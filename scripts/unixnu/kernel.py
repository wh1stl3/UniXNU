"""XNU kernel: build from the patched Apple source, then prelink against the original kernelcache."""
import os
import platform
import shlex
from pathlib import Path

from . import components, ipsw, patches
from .util import Error, expand, log, run, sha256_file, tool


def xnu_env(ctx):
    """CONFIG_XNU_* of the defconfig become XNU_* variables of the legacy kernel build script."""
    env = {}
    for key, value in ctx.need_config().items():
        if not key.startswith('XNU_'):
            continue
        if isinstance(value, str):
            value = value.replace('{tree}', str(ctx.tree))
        env[key] = '1' if value is True else '0' if value is False else str(value)
    return env


def version_env(modules, ctx=None):
    """Source versions of the Apple references, from feeds.toml, for the kernel scripts."""
    env = {}
    for name, prefix in (('xnu', 'XNU'), ('libplatform', 'LIBPLATFORM'), ('libdispatch', 'LIBDISPATCH'), ('AvailabilityVersions', 'AVAILABILITYVERSIONS')):
        module = modules.get(('refer', name))
        entry = module.source if module and module.source else {}
        if entry.get('ref'):
            env[f'UNIXNU_{prefix}_TAG'] = entry['ref']
        if entry.get('commit'):
            env[f'UNIXNU_{prefix}_COMMIT'] = entry['commit']
    xnu = (modules.get(('refer', 'xnu')) or None) and modules[('refer', 'xnu')].source or {}
    for key, variable in (('darwin', 'UNIXNU_XNU_DARWIN'), ('version', 'UNIXNU_XNU_VERSION'),
                          ('driverkit_tag', 'UNIXNU_DRIVERKIT_TAG'), ('trustcache_tag', 'UNIXNU_TRUSTCACHE_TAG')):
        if xnu.get(key):
            env[variable] = xnu[key]
    if ctx and ctx.schema_version == 2:
        profile = ctx.board.get('os', {})
        for key, variable in (('xnu_revision', 'UNIXNU_XNU_COMMIT'), ('xnu_version', 'UNIXNU_XNU_VERSION'),
                              ('darwin', 'UNIXNU_XNU_DARWIN'), ('driverkit_tag', 'UNIXNU_DRIVERKIT_TAG'),
                              ('trustcache_tag', 'UNIXNU_TRUSTCACHE_TAG')):
            if profile.get(key):
                env[variable] = profile[key]
        if profile.get('xnu_version'):
            env['UNIXNU_XNU_TAG'] = 'xnu-' + profile['xnu_version']
    return env


def toolchain_path(path=None):
    """PATH with the Homebrew LLVM and LLD first, as the archive builders expect."""
    extra = [d for d in ('/opt/homebrew/opt/llvm/bin', '/opt/homebrew/opt/lld/bin', '/usr/local/opt/llvm/bin', '/usr/local/opt/lld/bin')
             if Path(d).is_dir()]
    return os.pathsep.join(extra + [path if path is not None else os.environ.get('PATH', '')])


def linux_env(ctx):
    """Environment of the kernel step on a Linux host, with the toolchain of scripts/linux/setup-toolchain.py.

    The xcrun shim answers every --sdk query with the fakeroot this build makes. The target is plain arm64 for
    iOS 17, so the clang wrapper adds only the flag that keeps C++ static destructors in __mod_term_func.
    CCC_OVERRIDE_OPTIONS (read by the clang driver itself, so also by the archive builders that replay xnu's
    compile records) turns off two warnings that upstream clang has and Apple clang does not; the builders compile
    with -Werror.
    """
    toolchain = Path(os.environ.get('UNIXNU_TOOLCHAIN', '/opt/unixnu-linux'))
    clt, xctoolchain = toolchain / 'CommandLineTools/usr', toolchain / 'XcodeDefault.xctoolchain/usr'
    for path in (toolchain / 'llvm/bin/clang', clt / 'bin/ld', clt / 'bin/xnu-host-cc', clt / 'libexec/migcom',
                 xctoolchain / 'bin/iig', Path('/usr/bin/xcrun'), toolchain / 'bin/lzfse'):
        if not path.exists():
            raise Error(f'{path} missing; run "sudo scripts/linux/setup-toolchain.py {toolchain}"')
    fakeroot = ctx.tree / '.cache/fakeroot'
    return {'PATH': os.pathsep.join([str(clt / 'bin'), str(toolchain / 'bin'), os.environ.get('PATH', '')]),
            'LC_ALL': 'C', 'CLT_PREFIX': str(clt), 'XCTOOLCHAIN_PREFIX': str(xctoolchain),
            'XNU_TOOLCHAIN_BIN': f'{clt / "bin"} {xctoolchain / "bin"}',
            'UNIXNU_SDKROOT': str(fakeroot), 'UNIXNU_SDK_VERSION': '17.0',
            'UNIXNU_PLATFORM_PATH': str(fakeroot / 'Platforms/iPhoneOS.platform'),
            'CROSS_CLANG': str(toolchain / 'llvm/bin/clang'), 'DARWIN_TRIPLE': 'arm64-apple-ios17.0',
            'CROSS_EXTRA_FLAGS': '-mllvm -disable-atexit-based-global-dtor-lowering',
            'CCC_OVERRIDE_OPTIONS': '# +-Wno-missing-designated-field-initializers +-Wno-unused-but-set-global'}


def archive_plan(ctx):
    """Expand selected component recipes at their ordered archive positions."""
    entries = ctx.board.get('kernel', {}).get('archives', [])
    if ctx.schema_version == 1:
        return [('script', entry) for entry in entries]
    specs = {spec['id']: spec for spec in ctx.component_specs}
    required = {name for name, spec in specs.items() if spec.get('build') and spec.get('build_stage', 'kernel') == 'kernel'}
    result, visited = [], set()

    def add_component(identifier):
        if identifier in visited:
            return
        spec = specs.get(identifier)
        if spec is None:
            raise Error(f'[kernel] archives: component {identifier} is not selected')
        for dependency in spec.get('dependencies', []):
            add_component(dependency)
        visited.add(identifier)
        if identifier in required:
            result.append(('component', spec))

    explicit = any(entry.startswith('component:') for entry in entries)
    if not explicit:
        for identifier in specs:
            add_component(identifier)
    for entry in entries:
        if entry.startswith('component:'):
            add_component(entry[len('component:'):])
        else:
            result.append(('script', entry))
    missing = required - visited
    if missing:
        raise Error('[kernel] archives needs component entries for: ' + ', '.join(sorted(missing)))
    return result


def build_archives(ctx, env):
    """Build ordered component recipes and auxiliary archives from compile records."""
    if not ctx.need_config().get('XNU_BUILD_ARCHIVES'):
        return
    env = dict(env, PATH=toolchain_path(env.get('PATH')))
    for index, (kind, entry) in enumerate(archive_plan(ctx), 1):
        if kind == 'component':
            spec = entry
            module = ctx.modules[(spec['kind'], spec['id'])]
            replacements = {'tree': str(ctx.tree), 'component': str(module.path), 'out': str(ctx.work)}
            parts = [part.format(**replacements) for part in spec['build']]
            label = f'component-{spec["id"]}'
        else:
            parts = shlex.split(entry)
            label = f'archive-{index:02d}-{Path(parts[0]).stem}'
        executable = Path(parts[0])
        if executable.suffix in ('.py', '.sh'):
            script = executable if executable.is_absolute() else ctx.tree / 'scripts' / executable
            if not script.is_file():
                raise Error(f'{label}: build script missing: {script}')
            parts = ['python3' if executable.suffix == '.py' else 'bash', str(script), *parts[1:]]
        log(f'kernel: {label}')
        run(parts, cwd=ctx.tree, env=env, log_file=ctx.logs / f'{label}.log')
        components.sync_outputs(ctx, ctx.modules)
    for key, value in sorted(xnu_env(ctx).items()):
        if key.endswith('_ARCHIVE') and value.endswith('.a') and not Path(value).is_file():
            raise Error(f'{key}: {value} not found; supply the archive or its build recipe')


def build(ctx, modules):
    log('kernel: XNU')
    script = ctx.tree / 'scripts/build-xnu-4k-baseline.sh'
    if not script.is_file():
        raise Error(f'{script} missing')
    env = dict(os.environ)
    if platform.system() == 'Linux':
        for name in ('git', 'make', 'cmake', 'ninja', 'unifdef'):
            tool(name, 'run sudo scripts/linux/setup-toolchain.py')
        env.update(linux_env(ctx))
    else:
        for name in ('git', 'make', 'clang', 'cmake', 'ninja', 'unifdef'):
            tool(name, 'brew install ' + name)
        tool('xcodebuild', 'the kernel step builds with the Xcode iphoneos SDK')
    env.update(xnu_env(ctx))
    env.update(version_env(modules, ctx))
    if ctx.schema_version == 2:
        env['UNIXNU_PATCH_LIST'] = str(patches.prepare(ctx, modules))
        generated = ctx.tree / 'build/generated'
        generated.mkdir(parents=True, exist_ok=True)
        env['UNIXNU_GENERATED_DIR'] = str(generated)
    env['JOBS'] = str(ctx.jobs)
    record = ctx.tree / 'build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/osfmk/DEVELOPMENT/startup.o.json'
    if not record.is_file():
        # The archive builders and the boot progress layer read compile records of the XNU build, which only an earlier
        # pass leaves behind. A first build from scratch therefore runs one pass without them; XNU_BOOTSTRAP makes it
        # skip the archive checks and link without the archives, so it stops at the link and only the records are
        # required of it.
        log('kernel: bootstrap pass for the compile records')
        subprocess_env = {**env, 'XNU_BOOT_PROGRESS': '0', 'XNU_BOOTSTRAP': '1'}
        try:
            run(['bash', script], cwd=ctx.tree, env=subprocess_env, log_file=ctx.logs / 'kernel-bootstrap.log')
        except Error:
            if not record.is_file():
                raise
    storage = ctx.tree / 'build/storage-abi/include/IOKit/storage'
    if (ctx.tree / 'refer/IOStorageFamily').is_dir() and not storage.is_dir():
        log('kernel: prepare storage headers')
        run(['python3', ctx.tree / 'scripts/prepare-storage-headers.py'], cwd=ctx.tree, env=env,
            log_file=ctx.logs / 'storage-headers.log')
    spec = ctx.board.get('kernel', {}).get('prelink', {})
    static_storage = (ctx.schema_version == 2 and
        spec.get('kernelcache_sha256') == 'f18b4df865405f2a287b84977d7aca745e056d656d9fc9df1662970ce2969de7')
    if static_storage:
        cache = storage_donor(ctx, spec)
        run(['python3', ctx.tree / 'scripts/audit-storage-interface.py',
             '--static-donor', cache, f'--slide={spec["slide"]}'], cwd=ctx.tree, env=env,
            log_file=ctx.logs / 'storage-static.log')
        env['UNIXNU_STORAGE_STATIC'] = '1'
        pmgr = ctx.tree / 'scripts/build-sheng-platform-power.py'
        if pmgr.is_file():
            run(['python3', ctx.tree / 'scripts/prepare-sheng-font.py'], cwd=ctx.tree,
                env=env, log_file=ctx.logs / 'sheng-font.log')
            run(['python3', ctx.tree / 'scripts/prepare-sheng-gpu-inputs.py'], cwd=ctx.tree,
                env=env, log_file=ctx.logs / 'sheng-gpu-inputs.log')
            import hashlib
            import shutil
            actual = hashlib.sha256(pmgr.read_text().encode()).hexdigest()
            if actual != 'c0b0932168ec2b7276bc033a725a5f97448af898efc5f5f2538f72a8324459b1':
                raise Error('Unrecognized Sheng PMGR builder; refusing offline adaptation')
            shutil.copyfile(ctx.tree / 'scripts/data/build-sheng-platform-power-static.py', pmgr)
            env['UNIXNU_STATIC_DONOR'] = str(cache)
            env['UNIXNU_ORIGINAL_DONOR'] = str(cache)
            env['UNIXNU_STATIC_SLIDE'] = str(int(str(spec['slide']), 0))
            display = ctx.tree / 'scripts/build-gop-legacy-display.py'
            if hashlib.sha256(display.read_text().encode()).hexdigest() != '93e4bd23912dcbd26f090f7cf1f5b62fcb92a185c8e35dd5e0968deb31ebe777':
                raise Error('Unrecognized Sheng display builder')
            shutil.copyfile(ctx.tree / 'scripts/data/build-gop-legacy-display-static.py', display)
            run(['python3', ctx.tree / 'scripts/build-sheng-hid-input.py', '--prepare-only'],
                cwd=ctx.tree, env=env, log_file=ctx.logs / 'hid-header.log')

    build_archives(ctx, env)
    run(['bash', script], cwd=ctx.tree, env=env, log_file=ctx.logs / 'kernel.log')


def storage_donor(ctx, spec):
    cache = ctx.option('kernelcache', 'UNIXNU_KERNELCACHE') or (expand(ctx.tree / spec['kernelcache']) if spec.get('kernelcache') else None)
    if not cache:
        cache = ipsw.kernelcache(ctx, ipsw.Ipsw(ctx))
    if not cache.is_file() or sha256_file(cache) != spec['kernelcache_sha256']:
        raise Error('Storage donor identity mismatch')
    return cache


def prelink(ctx):
    """Produce out/<device>/kernel/kernel.macho from the XNU build and the original kernelcache."""
    log('kernel: prelink')
    spec = ctx.board.get('kernel', {}).get('prelink')
    if not spec:
        raise Error('board.toml has no [kernel.prelink]')
    cache = ctx.option('kernelcache', 'UNIXNU_KERNELCACHE') or (expand(ctx.tree / spec['kernelcache']) if spec.get('kernelcache') else None)
    if not cache:
        # Not given: take it from the IPSW (--ipsw PATH_OR_URL, or the url of board.toml [ipsw]).
        cache = ipsw.kernelcache(ctx, ipsw.Ipsw(ctx))
    if not cache.is_file():
        raise Error(f'kernelcache not found: {cache}')
    wanted = spec.get('kernelcache_sha256')
    if wanted and sha256_file(cache) != wanted:
        raise Error(f'{cache} does not match the kernelcache this board was qualified against (sha256 {wanted})')
    kernel = ctx.tree / spec['kernel']
    if not kernel.is_file():
        raise Error(f'{kernel} not found; run "unixnu build kernel" first')
    output = ctx.work / 'kernel/kernel.macho'
    output.parent.mkdir(parents=True, exist_ok=True)
    # emit_prelink refuses to overwrite; a rebuild replaces the previous candidate and its record.
    for stale in (output, output.with_suffix('.json')):
        stale.unlink(missing_ok=True)
    command = ['python3', ctx.tree / spec['tool'], '--kernel', kernel, '--prelinked', cache,
               f'--slide={spec["slide"]}', '--output', output]
    for root in spec.get('roots', []):
        command += ['--root', root]
    if spec.get('early_security_init'):
        command += ['--early-security-init', spec['early_security_init']]
    command += spec.get('extra_args', [])
    run(command, cwd=ctx.tree, log_file=ctx.logs / 'prelink.log')
    if (ctx.schema_version == 2 and
        spec.get('kernelcache_sha256') == 'f18b4df865405f2a287b84977d7aca745e056d656d9fc9df1662970ce2969de7'):
        run(['python3', ctx.tree / 'scripts/verify-storage-prelink.py', output],
            cwd=ctx.tree, log_file=ctx.logs / 'storage-final.log')
    if (ctx.tree / 'build/sheng-platform-power/build-report.json').is_file():
        run(['python3', ctx.tree / 'scripts/audit-amfi-pmgr-contract.py', '--candidate', output],
            cwd=ctx.tree, env={**os.environ, 'UNIXNU_ORIGINAL_DONOR': str(cache)},
            log_file=ctx.logs / 'pmgr-final.log')
    if (ctx.tree / 'build/native-legacy-display/build-report.json').is_file():
        run(['python3', ctx.tree / 'scripts/verify-display-prelink.py', output],
            cwd=ctx.tree, log_file=ctx.logs / 'display-final.log')
    log(f'kernel: {output} sha256 {sha256_file(output)}')
    return output
