"""把 build_log.txt 也复制到 audit_pack_src/，再重新打包（确保审计方解压后看到全部 SHA）"""
import os, shutil

src = r'D:\个股工作台\output\20260910-audit\build_log.txt'
dst = r'D:\个股工作台\audit_pack_src\build_log.txt'

shutil.copy2(src, dst)
print('COPIED build_log.txt to audit_pack_src')
print('SIZE=', os.path.getsize(dst))