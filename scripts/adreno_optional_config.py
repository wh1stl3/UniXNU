"""Scope optional Adreno declarations to their existing command-db consumers."""
BLOCKS = (
'''                const size_t ring_bytes=0x8000,fence_bytes=0x1000;
                const uint64_t ring_iova=0,fence_iova=0,sqe_iova=0,pwrup_iova=0;
                const uint64_t sqe_bytes=(reinterpret_cast<uintptr_t>(&native_adreno_sqe_firmware_image_size)&&
                    reinterpret_cast<uintptr_t>(native_adreno_sqe_firmware_image))?
                    ((native_adreno_sqe_firmware_image_size+0xfff)&~UINT64_C(0xfff)):0;
''',
'''                NativeAdrenoGmuAllocator &gmu_=gmu_ctx_.allocator();
                NativeAdrenoVm &vm_=gmu_ctx_.vm();
''')

def guard_optional_declarations(source):
    for block in BLOCKS:
        if source.count(block) != 1:
            raise ValueError('Adreno optional declaration source changed; review adaptation')
        source = source.replace(block, '#ifdef NATIVE_ADRENO_HAVE_COMMAND_DB\n' + block + '#endif\n')
    return source
