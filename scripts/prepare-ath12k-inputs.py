#!/usr/bin/env python3
"""Fetch exact public Ath12k build dependencies before generated include preparation."""
import json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DEPENDENCIES={
 'linux':('https://github.com/gregkh/linux.git','458c6079fc1d41d564c37679c8ace02cd83ee817',
          ['/drivers/net/wireless/ath/','/drivers/bus/mhi/','/include/linux/mhi.h','/include/linux/ieee80211*.h','/include/linux/soc/qcom/qmi.h','/include/net/cfg80211.h','/include/net/regulatory.h','/include/net/codel.h','/include/net/ieee80211_radiotap.h','/include/net/mac80211.h','/include/uapi/linux/nl80211.h','/include/uapi/linux/rfkill.h','/net/qrtr/','/drivers/soc/qcom/qmi_interface.c','/drivers/soc/qcom/qmi_encdec.c']),
 'freebsd':('https://github.com/freebsd/freebsd-src.git','95719d8a895bf8170851e9844d9b4092b1d2b6fe',
            ['/sys/compat/linuxkpi/','/sys/net80211/','/sys/sys/']),
}
def run(*args):return subprocess.check_output([str(a) for a in args],text=True).strip()
def prepare(module):
    module=module.resolve()
    if run('git','-C',module,'rev-parse','HEAD')!='f6bf561f92cc42761bdd417fce1d53fe1db9477c':
        raise ValueError('Unexpected Ath12kWifi revision')
    records={}
    for name,(url,revision,paths) in DEPENDENCIES.items():
        target=module/'deps'/name
        if not target.exists():
            target.mkdir(parents=True)
            run('git','init',target)
            run('git','-C',target,'remote','add','origin',url)
        if not (target/'.git').is_dir():
            raise ValueError('Dependency directory is not its own Git checkout: '+name)
        head=subprocess.run(['git','-C',str(target),'rev-parse','--verify','HEAD'],capture_output=True,text=True)
        if head.returncode:
            if run('git','-C',target,'status','--porcelain'):
                raise ValueError('Refusing to resume populated uncommitted dependency: '+name)
            run('git','-C',target,'remote','set-url','origin',url)
            run('git','-C',target,'config','remote.origin.promisor','true')
            run('git','-C',target,'config','remote.origin.partialclonefilter','blob:none')
            run('git','-C',target,'fetch','--depth=1','--filter=blob:none','origin',revision)
            run('git','-C',target,'sparse-checkout','set','--no-cone',*paths)
            run('git','-C',target,'checkout','--detach',revision)
        if run('git','-C',target,'rev-parse','HEAD')!=revision or run('git','-C',target,'status','--porcelain','--untracked-files=no'):
            raise ValueError('Ath12k dependency revision or tracked content differs: '+name)
        records[name]=dict(repository=url,revision=revision)
    for name in ('drivers/bus/mhi/host/boot.c','drivers/net/wireless/ath/ath12k/dp.h'):
        if not (module/'deps/linux'/name).is_file():raise ValueError('Sparse input missing: '+name)
    out=ROOT/'build/ath12k-inputs';out.mkdir(parents=True,exist_ok=True)
    (out/'sources.json').write_text(json.dumps(records,indent=2)+'\n')
    print('PASS: exact Linux v7.0.14 and FreeBSD 15.1 dependency checkouts')
if __name__=='__main__':prepare(Path(sys.argv[1]))
