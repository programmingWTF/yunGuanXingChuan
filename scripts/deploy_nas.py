"""NAS 部署脚本 - 通过 SSH/SFTP 同步代码到 NAS 并重建 Docker 容器"""
import getpass
import os
import subprocess
import sys
from pathlib import Path

try:
    import paramiko
except ImportError:
    print("安装 paramiko...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "paramiko", "-q"])
    import paramiko

# 凭据通过环境变量注入，避免明文入库（建议在 shell profile 中 export）：
#   NAS_HOST       NAS 地址，默认 192.168.0.150
#   NAS_USER       登录用户名，默认 LiGuiyu
#   NAS_PASSWORD   登录密码，未设置则运行时交互式输入
HOST = os.getenv("NAS_HOST", "192.168.0.150")
USER = os.getenv("NAS_USER", "LiGuiyu")
PASSWORD = os.getenv("NAS_PASSWORD", "")

DOCKER_DIR = "/vol1/1000/Docker/yunguanxingchuan"
LOCAL_DIR = Path(__file__).parent.parent  # yunGuanXingChuan 项目根目录

# 需要同步的目录/文件（排除 node_modules, dist, __pycache__, .git, env 等）
SYNC_DIRS = ["api", "config", "src", "scripts", "frontend/src", "frontend"]
SYNC_FILES = [
    "docker-compose.yml", "Dockerfile", ".dockerignore",
    "requirements.txt", "pyproject.toml",
    "frontend/index.html", "frontend/package.json",
    "frontend/package-lock.json", "frontend/vite.config.ts",
    "frontend/tsconfig.json", "frontend/tsconfig.node.json",
    "frontend/tailwind.config.js", "frontend/postcss.config.js",
]
SKIP_DIRS = {"node_modules", "__pycache__", ".git", ".pytest_cache", ".remember", ".claude"}


def ensure_password() -> str:
    """优先使用环境变量 NAS_PASSWORD，否则运行时交互式输入（不回显）"""
    global PASSWORD
    if not PASSWORD:
        PASSWORD = getpass.getpass(f"请输入 {USER}@{HOST} 的密码: ")
    return PASSWORD


def run_cmd(ssh, cmd, sudo=False):
    """执行远程命令并打印输出"""
    if sudo:
        cmd = f"echo '{PASSWORD}' | sudo -S sh -c '{cmd}'"
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=300)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out.strip():
        print(out.strip())
    if err.strip():
        err_lines = [l for l in err.strip().splitlines()
                     if "[sudo]" not in l and "password" not in l.lower()]
        if err_lines:
            print("\n".join(err_lines))
    return out


def sftp_mkdir_p(sftp, remote_dir):
    """递归创建远程目录"""
    dirs_to_create = []
    d = remote_dir
    while True:
        try:
            sftp.stat(d)
            break
        except FileNotFoundError:
            dirs_to_create.append(d)
            d = os.path.dirname(d)
            if d == "/" or d == "":
                break
    for d in reversed(dirs_to_create):
        try:
            sftp.mkdir(d)
        except IOError:
            pass


def should_skip(path: Path) -> bool:
    """判断是否跳过"""
    parts = path.parts
    for skip in SKIP_DIRS:
        if skip in parts:
            return True
    if path.suffix in (".pyc", ".coverage"):
        return True
    return False


def sync_directory(sftp, local_base: Path, remote_base: str, sub_dir: str):
    """同步一个子目录"""
    local_path = local_base / sub_dir
    remote_path = f"{remote_base}/{sub_dir}"
    if not local_path.exists():
        return 0

    count = 0
    for root, dirs, files in os.walk(local_path):
        # 过滤跳过的目录
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        rel_root = Path(root).relative_to(local_base)
        remote_root = f"{remote_base}/{rel_root.as_posix()}"
        sftp_mkdir_p(sftp, remote_root)

        for fname in files:
            fpath = Path(root) / fname
            if should_skip(fpath.relative_to(local_base)):
                continue
            remote_file = f"{remote_root}/{fname}"
            sftp.put(str(fpath), remote_file)
            count += 1
    return count


def main():
    ensure_password()
    print(f"连接 {USER}@{HOST}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=15)
    print("连接成功!")

    sftp = ssh.open_sftp()

    # 1. 同步关键文件
    print("\n[1/3] 同步代码文件...")
    total = 0

    # 同步单文件
    for rel_file in SYNC_FILES:
        local_file = LOCAL_DIR / rel_file
        if local_file.exists():
            remote_file = f"{DOCKER_DIR}/{rel_file}"
            sftp_mkdir_p(sftp, os.path.dirname(remote_file))
            sftp.put(str(local_file), remote_file)
            total += 1

    # 同步目录（排除 frontend 整体，只同步 frontend/src）
    for sub in ["api", "config", "src", "scripts"]:
        n = sync_directory(sftp, LOCAL_DIR, DOCKER_DIR, sub)
        total += n
        print(f"  {sub}/ -> {n} 个文件")

    # frontend/src
    n = sync_directory(sftp, LOCAL_DIR, DOCKER_DIR, "frontend/src")
    total += n
    print(f"  frontend/src/ -> {n} 个文件")

    # frontend/dist (Docker 镜像实际使用的前端产物)
    n = sync_directory(sftp, LOCAL_DIR, DOCKER_DIR, "frontend/dist")
    total += n
    print(f"  frontend/dist/ -> {n} 个文件")

    # data/kg (知识图谱)
    n = sync_directory(sftp, LOCAL_DIR, DOCKER_DIR, "data/kg")
    total += n
    print(f"  data/kg/ -> {n} 个文件")

    print(f"  共同步 {total} 个文件")
    sftp.close()

    # 2. 重建 Docker 容器
    print("\n[2/3] 重建 Docker 容器...")
    run_cmd(ssh, f"cd {DOCKER_DIR} && docker compose up -d --build", sudo=True)

    # 3. 检查容器状态
    print("\n[3/3] 检查容器状态...")
    run_cmd(ssh, "docker ps --filter name=yunguanxingchuan", sudo=True)

    ssh.close()
    print("\n[OK] 部署完成! 访问 http://192.168.0.150:8123")


if __name__ == "__main__":
    main()
