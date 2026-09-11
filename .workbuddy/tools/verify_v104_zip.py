"""验证 v1.0.4 最终发版 ZIP 的 SHA 自洽性。"""
import os
import re
import zipfile
import hashlib


ZPATH = r'D:\个股工作台\个股工作台-v1.0.4-20260910.zip'


def sha256_data(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    print(f'ZIP 路径: {ZPATH}')
    zip_size = os.path.getsize(ZPATH)
    zip_h = hashlib.sha256()
    with open(ZPATH, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            zip_h.update(chunk)
    print(f'ZIP 大小: {zip_size} bytes ({zip_size / 1024:.1f} KB)')
    print(f'ZIP SHA-256: {zip_h.hexdigest()}')
    print()

    z = zipfile.ZipFile(ZPATH, 'r')
    files = sorted(z.namelist())
    print(f'内含文件数: {len(files)}')
    print()

    # 1) manifest 自洽
    manifest_text = z.read('PACK_MANIFEST.md').decode('utf-8')
    print('【1】PACK_MANIFEST.md 自洽验证')
    file_shas = []
    for line in manifest_text.split('\n'):
        m = re.match(r'\| (\d+) \| `(.+?)` \| (\d+) \| `([a-f0-9]{64})` \|', line)
        if m:
            idx, path, sz, sha = m.groups()
            file_shas.append((path, int(sz), sha))
    print(f'  manifest 列出 {len(file_shas)} 个送审文件条目')

    ok = 0
    bad_list = []
    for path, exp_sz, exp_sha in file_shas:
        try:
            real = z.read(path)
        except KeyError:
            bad_list.append(f'  [缺失] {path}')
            continue
        real_sz = len(real)
        real_sha = sha256_data(real)
        if real_sha == exp_sha and real_sz == exp_sz:
            ok += 1
        else:
            bad_list.append(
                f'  [不匹配] {path}\n'
                f'    期望: SIZE={exp_sz}  SHA={exp_sha}\n'
                f'    实际: SIZE={real_sz}  SHA={real_sha}'
            )
    print(f'  PASS: {ok}/{len(file_shas)}')
    if bad_list:
        for b in bad_list:
            print(b)
    else:
        print('  全部一致 ✓')
    print()

    # 2) 检查 manifest 自身是否存在
    manifest_data = z.read('PACK_MANIFEST.md')
    print('【2】PACK_MANIFEST.md 自身完整性')
    print(f'  大小: {len(manifest_data)} bytes')
    print(f'  SHA-256: {sha256_data(manifest_data)}')
    print('  (清单不预存自身 SHA，接收方可独立验证)')
    print()

    # 3) 检查 PACK_NOTES.md 内容可读
    notes = z.read('PACK_NOTES.md').decode('utf-8')
    print('【3】PACK_NOTES.md 内容可读性')
    has_version = 'v1.0.4' in notes
    has_fix_count = 'v1.0.4 关键修复' in notes
    print(f'  含 v1.0.4 标识: {has_version}')
    print(f'  含关键修复节: {has_fix_count}')
    print(f'  首行预览: {notes.split(chr(10))[0]}')
    print()

    print('=' * 50)
    print(f'ZIP 自洽: {"PASS" if ok == len(file_shas) else "FAIL"}')
    print('=' * 50)


if __name__ == '__main__':
    main()
