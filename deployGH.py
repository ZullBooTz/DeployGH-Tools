import os
import sys
import time
import json
import re
import logging
import importlib
import subprocess
import threading
import itertools
import base64
import shutil
from datetime import datetime

CONFIG_FILE = "github_config.json"

done_loading = False

def animate_install(text: str):
    spinner = itertools.cycle(['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'])
    while not done_loading:
        sys.stdout.write(f"\r\033[1;33m{next(spinner)} {text}...\033[0m")
        sys.stdout.flush()
        time.sleep(0.1)
    sys.stdout.write("\r\033[K")

def check_and_install(package_name: str):
    global done_loading
    try:
        importlib.import_module(package_name)
    except ImportError:
        print(f"\033[1;31m[!] Modul '{package_name}' belum terdeteksi.\033[0m")
        done_loading = False
        t = threading.Thread(target=animate_install, args=(f"Instalasi {package_name}",))
        t.start()
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            done_loading = True
            t.join() 
        except Exception:
            done_loading = True
            sys.exit(1)

check_and_install('rich')
check_and_install('requests') 

import requests
from rich.console import Console
from rich.panel import Panel
from rich.align import Align
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.table import Table
from rich import box

class TakazGitHubManager:
    def __init__(self):
        self.console = Console()

    def header(self, title_text):
        os.system('cls' if os.name == 'nt' else 'clear')
        ascii_art = r"""
  ____ ___ _____ _   _ _   _ ____  
 / ___|_ _|_   _| | | | | | | __ ) 
| |  _  | | | | | |_| | | | |  _ \ 
| |_| | | | | | |  _  | |_| | |_) |
 \____|___| |_| |_| |_|\___/|____/ 
 _   _ ____  _     ___    _    ____  _____ ____  
| | | |  _ \| |   / _ \  / \  |  _ \| ____|  _ \ 
| | | | |_) | |  | | | |/ _ \ | | | |  _| | |_) |
| |_| |  __/| |__| |_| / ___ \| |_| | |___|  _ < 
 \___/|_|   |_____\___/_/   \_\____/|_____|_| \_\
"""
        panel = Panel(Align.center(f"[bold blue]{ascii_art}[/bold blue]\n[bold cyan][ ✦ TAKAZ V5 {title_text} ✦ ][/bold cyan]"), border_style="bold blue")
        self.console.print(panel)
        self.console.print("")

    def run_cmd_capture(self, command: str) -> tuple:
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, 
                text=True, encoding="utf-8", errors="replace"
            )
            return result.returncode == 0, result.stdout + result.stderr
        except Exception as e:
            return False, str(e)

    def get_saved_credentials(self) -> dict:
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    data['token'] = base64.b64decode(data['token']).decode('utf-8')
                    return data
            except Exception:
                pass
        return {}

    def save_credentials(self, username, token):
        encoded_token = base64.b64encode(token.encode()).decode('utf-8')
        with open(CONFIG_FILE, "w") as f:
            json.dump({'username': username, 'token': encoded_token}, f, indent=4)

    def fetch_repositories(self, token: str) -> list:
        with Progress(
            SpinnerColumn("dots", style="bold cyan"),
            TextColumn("[bold cyan]Menghubungkan ke GitHub dan mengambil daftar repository...[/bold cyan]"),
            transient=True,
            console=self.console
        ) as progress:
            task = progress.add_task("", total=None)
            headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
            try:
                response = requests.get("https://api.github.com/user/repos?per_page=100&sort=updated", headers=headers, timeout=10)
                if response.status_code == 200:
                    return response.json()
                else:
                    self.console.print(f"[bold red]❌ Gagal ambil repo: {response.status_code} - {response.json().get('message', '')}[/bold red]")
                    return []
            except Exception as e:
                self.console.print(f"\n[bold red]❌ Error koneksi API: {e}[/bold red]")
                return []

    def select_repository(self, token: str) -> dict:
        repos = self.fetch_repositories(token)
        if not repos: return None
        
        table = Table(box=box.ROUNDED, expand=True, border_style="bold blue")
        table.add_column("No", justify="center", style="cyan", width=4)
        table.add_column("Nama Repository", style="bold green")
        table.add_column("Visibilitas", style="yellow", justify="center", width=12)
        table.add_column("Update Terakhir", style="white")
        
        for idx, repo in enumerate(repos, 1):
            vis = "[red]Private[/red]" if repo['private'] else "[green]Public[/green]"
            date_str = repo['updated_at'][:10]
            table.add_row(str(idx), repo['name'], vis, date_str)
            
        self.console.print(table)
        self.console.print("[italic grey50]* Jika repository tidak ada di list, ketik '0' untuk memasukkan URL secara manual.[/italic grey50]")
        
        choice = Prompt.ask(f"\n[bold green]➜ Pilih Repository (1-{len(repos)}) atau 0 untuk Manual[/bold green]")
        if choice == "0": return {} 
            
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(repos): return repos[idx]
            else:
                self.console.print("[bold red][!] Pilihan tidak valid.[/bold red]")
                return None
        except ValueError:
            self.console.print("[bold red][!] Input harus angka.[/bold red]")
            return None

    def cleanup_git_state(self):
        commands = [
            "git rebase --abort",
            "git merge --abort",
            "git cherry-pick --abort",
            "git am --abort",
        ]
        for cmd in commands:
            self.run_cmd_capture(cmd)
            
        if os.path.exists(".git/rebase-merge"):
            shutil.rmtree(".git/rebase-merge", ignore_errors=True)
        if os.path.exists(".git/rebase-apply"):
            shutil.rmtree(".git/rebase-apply", ignore_errors=True)

    def secure_gitignore(self):
        """Memastikan github_config.json dan folder cache tidak ikut terupload."""
        ignore_items = [CONFIG_FILE, ".takaz_cache/", "__pycache__/", "*.pyc"]
        if not os.path.exists(".gitignore"):
            with open(".gitignore", "w", encoding="utf-8") as f:
                f.write("\n".join(ignore_items) + "\n")
        else:
            with open(".gitignore", "r", encoding="utf-8") as f:
                content = f.read()
            with open(".gitignore", "a", encoding="utf-8") as f:
                for item in ignore_items:
                    if item not in content:
                        f.write(f"\n{item}\n")

    def smart_sync_and_push(self, progress, task_sync, task_push, branch_name) -> tuple:
        progress.update(task_sync, description="[cyan]Membersihkan status Git lokal...[/cyan]")
        self.cleanup_git_state()

        progress.update(task_sync, description="[cyan]Fetching data dari GitHub...[/cyan]")
        self.run_cmd_capture("git fetch origin")

        success, ls_out = self.run_cmd_capture(f"git ls-remote --heads origin {branch_name}")
        remote_exists = bool(ls_out.strip())

        if remote_exists:
            progress.update(task_sync, description=f"[cyan]Rebasing dengan origin/{branch_name}...[/cyan]")
            ok_rebase, rebase_out = self.run_cmd_capture(f"git rebase origin/{branch_name}")

            if not ok_rebase:
                self.cleanup_git_state()
                
                if "unrelated histories" in rebase_out.lower() or "fatal: refusing to merge" in rebase_out.lower():
                    progress.update(task_sync, description="[yellow]Menyatukan histori lokal & GitHub (Unrelated Histories)...[/yellow]")
                    ok_merge, merge_out = self.run_cmd_capture(f"git merge origin/{branch_name} --allow-unrelated-histories -X ours --no-edit")
                    if not ok_merge:
                        self.cleanup_git_state()
                        return False, f"Gagal menyatukan histori:\n{merge_out}"
                        
                elif "conflict" in rebase_out.lower() or "could not apply" in rebase_out.lower():
                    progress.update(task_sync, description="[yellow]Konflik terdeteksi! Memaksa menggunakan versi LOKAL (Auto-Resolve)...[/yellow]")
                    ok_force, force_out = self.run_cmd_capture(f"git rebase -X theirs origin/{branch_name}")
                    
                    if not ok_force:
                        self.cleanup_git_state()
                        progress.update(task_sync, description="[yellow]Rebase gagal, mencoba Auto-Merge...[/yellow]")
                        ok_merge2, merge_out2 = self.run_cmd_capture(f"git merge origin/{branch_name} -X ours --no-edit")
                        if not ok_merge2:
                            self.cleanup_git_state()
                            return False, f"Konflik sangat rumit, gagal Auto-Resolve:\n{force_out}\n{merge_out2}"
                else:
                    return False, f"Gagal Sinkronisasi Git:\n{rebase_out}"

        progress.update(task_sync, description="[bold green]✔ Sinkronisasi Selesai.[/bold green]")
        progress.update(task_push, description=f"[bold cyan]🚀 Memulai Upload ke Branch '{branch_name}'...[/bold cyan]")
        
        push_success = False
        push_output = ""

        for attempt in range(3):
            ok_push, push_out = self.run_cmd_capture(f"git push --set-upstream origin HEAD:{branch_name}")
            
            if ok_push:
                push_success = True
                break
                
            push_output = push_out

            if "non-fast-forward" in push_out.lower() or "fetch first" in push_out.lower():
                progress.update(task_push, description=f"[yellow]Non-Fast-Forward. Auto-Fixing (Percobaan {attempt+1}/3)...[/yellow]")
                self.cleanup_git_state()
                self.run_cmd_capture("git fetch origin")
                
                ok_retry, retry_out = self.run_cmd_capture(f"git rebase -X theirs origin/{branch_name}")
                if not ok_retry:
                    self.cleanup_git_state()
                    ok_retry_merge, retry_merge_out = self.run_cmd_capture(f"git merge origin/{branch_name} -X ours --no-edit")
                    if not ok_retry_merge:
                        self.cleanup_git_state()
                        return False, f"Gagal bypass saat Auto-Retry Push:\n{retry_out}\n{retry_merge_out}"
                continue
                
            break 

        if push_success:
            progress.update(task_push, description="[bold green]✔ Upload Data Sukses.[/bold green]")
            return True, ""
        else:
            return False, push_output

    # ============================================================
    # MENU 1: GITHUB UPLOADER
    # ============================================================
    def upload_repo(self):
        self.header("GITHUB UPLOADER")
        
        target_dir = Prompt.ask("[bold cyan]📁 Masukkan path folder yang mau diupload[/bold cyan]").strip()
        
        if not os.path.exists(target_dir) or not os.path.isdir(target_dir):
            self.console.print("[bold red][!] Folder tidak ditemukan![/bold red]")
            Prompt.ask("\n[bold white]ENTER[/bold white] untuk kembali")
            return

        os.chdir(target_dir)
        self.console.print(f"[bold green]✔ Masuk ke folder:[/bold green] {target_dir}")
        
        self.secure_gitignore()
        self.run_cmd_capture(f"git config --global --add safe.directory '{target_dir}'")
        
        saved = self.get_saved_credentials()
        if saved and Prompt.ask(f"\n[bold green]➜ Gunakan akun tersimpan ({saved['username']})? (y/n)[/bold green]", choices=["y", "n"], default="y") == "y":
            username = saved['username']
            token = saved['token']
        else:
            username = Prompt.ask("\n[bold blue]👤 GitHub Username[/bold blue]").strip()
            token = Prompt.ask("[bold yellow]🔑 GitHub Token (classic)[/bold yellow]", password=True).strip()
            if username and token: 
                self.save_credentials(username, token)
                
        if not username or not token: return
        
        repo = self.select_repository(token)
        if repo is None: 
            Prompt.ask("\n[bold white]ENTER[/bold white] untuk kembali")
            return
            
        if not repo:
            repo_url = Prompt.ask("[bold cyan]🔗 Masukkan Repository URL Manual (https://...)[/bold cyan]").strip()
            if not repo_url: return
        else:
            repo_url = repo['clone_url']
            self.console.print(f"\n[bold green]✔ Repository Terpilih:[bold white] {repo['name']}[/bold white]")
        
        if repo_url.startswith("https://"):
            auth_url = repo_url.replace("https://", f"https://{username}:{token}@")
        else:
            self.console.print("[bold red][!] URL harus diawali dengan https://[/bold red]")
            time.sleep(2)
            return

        if not os.path.exists(".git"):
            self.run_cmd_capture("git init")
            
        ok, _ = self.run_cmd_capture("git config user.name")
        if not ok: self.run_cmd_capture(f'git config user.name "{username}"')
            
        ok, _ = self.run_cmd_capture("git config user.email")
        if not ok: self.run_cmd_capture(f'git config user.email "{username}@users.noreply.github.com"')
            
        success, _ = self.run_cmd_capture("git remote get-url origin")
        if success: self.run_cmd_capture(f"git remote set-url origin {auth_url}")
        else: self.run_cmd_capture(f"git remote add origin {auth_url}")

        with Progress(
            SpinnerColumn("dots", style="bold cyan"),
            TextColumn("[progress.description]{task.description}"),
            transient=False,
            console=self.console
        ) as progress:
            
            task_add = progress.add_task("[yellow]Adding files...[/yellow]", total=None)
            self.run_cmd_capture("git add .")
            progress.update(task_add, description="[bold green]✔ Files added.[/bold green]")

            ok, _ = self.run_cmd_capture("git rev-parse --verify HEAD")
            if not ok:
                task_commit = progress.add_task("[yellow]Repository baru, membuat Initial Commit...[/yellow]", total=None)
                ok_commit, out_commit = self.run_cmd_capture('git commit -m "Initial Commit"')
                if not ok_commit: ok_commit, out_commit = self.run_cmd_capture('git commit --allow-empty -m "Initial Commit"')
                if not ok_commit:
                    progress.stop()
                    self.console.print(f"[bold red]❌ Gagal Initial Commit:\n{out_commit}[/bold red]")
                    Prompt.ask("\n[bold white]ENTER[/bold white] untuk kembali")
                    return
                self.run_cmd_capture("git branch -M main")
                progress.update(task_commit, description="[bold green]✔ Initial Commit sukses.[/bold green]")
            else:
                task_commit = progress.add_task("[yellow]Checking for changes...[/yellow]", total=None)
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                success, output = self.run_cmd_capture(f'git commit -m "Auto Update: {timestamp}"')
                if "nothing to commit" in output.lower() or not success:
                    progress.update(task_commit, description="[bold yellow]⚠️ Ga ada perubahan, skip commit[/bold yellow]")
                else:
                    progress.update(task_commit, description="[bold green]✔ Perubahan di-commit.[/bold green]")

            _, branch_out = self.run_cmd_capture("git rev-parse --abbrev-ref HEAD")
            branch_name = branch_out.strip()
            if not branch_name or branch_name == "HEAD":
                branch_name = "main"
                self.run_cmd_capture(f"git branch -M {branch_name}")

            task_sync = progress.add_task("[cyan]Sinkronisasi Data...[/cyan]", total=None)
            task_push = progress.add_task("[cyan]Antrean Upload...[/cyan]", total=None)
            
            final_success, error_msg = self.smart_sync_and_push(progress, task_sync, task_push, branch_name)

        if final_success:
            self.console.print("\n[bold green]✅ Upload sukses![/bold green]")
        else:
            self.console.print("\n[bold red]❌ Upload gagal! Git Error:[/bold red]")
            self.console.print(f"[red]{error_msg}[/red]")
        
        Prompt.ask("\n[bold white]ENTER[/bold white] untuk kembali")

    # ============================================================
    # MENU 2: RAW GITHUB RUNNER (FIXED PRIVATE & UNBUFFERED)
    # ============================================================
    def run_raw_script(self):
        self.header("RAW SCRIPT RUNNER")
        
        url = Prompt.ask("[bold cyan]🔗 Masukkan Link GitHub Raw (.py)[/bold cyan]").strip()
        if not url.startswith("http"):
            self.console.print("[bold red]❌ Error: Harap masukkan URL yang valid![/bold red]")
            Prompt.ask("\n[bold white]ENTER[/bold white] untuk kembali")
            return

        CACHE_DIR = ".takaz_cache"
        if not os.path.exists(CACHE_DIR):
            os.makedirs(CACHE_DIR)
            
        file_name = url.split("/")[-1]
        if not file_name.endswith(".py"):
            file_name += ".py"
            
        cache_file = os.path.join(CACHE_DIR, file_name)

        # Autentikasi untuk mendownload dari Private Repo
        headers = {}
        saved = self.get_saved_credentials()
        if saved and 'token' in saved:
            headers['Authorization'] = f"token {saved['token']}"

        with Progress(
            SpinnerColumn("dots12", style="cyan"), 
            TextColumn("[cyan]Memuat script dari GitHub Raw..."), 
            transient=True,
            console=self.console
        ) as progress:
            progress.add_task("download", start=False)
            try:
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                with open(cache_file, "w", encoding="utf-8") as f:
                    f.write(response.text)
                download_success = True
            except requests.exceptions.RequestException as e:
                download_success = False
                err_msg = str(e)
        
        if not download_success:
            if os.path.exists(cache_file):
                self.console.print("[bold yellow]⚠ Koneksi/Autentikasi gagal. Menggunakan versi Cache (Offline Mode).[/bold yellow]")
            else:
                self.console.print(f"[bold red]❌ Gagal mendownload script: {err_msg}[/bold red]")
                self.console.print("[italic yellow]* Jika ini Private Repo, pastikan Anda sudah menggunakan 'Menu 1' sebelumnya agar token Anda tersimpan di sistem.[/italic yellow]")
                Prompt.ask("\n[bold white]ENTER[/bold white] untuk kembali")
                return

        self.console.print(f"\n[bold green]▶ Menjalankan:[/bold green] [cyan]{file_name}[/cyan]\n" + "═"*45)
        
        while True:
            # Menggunakan flag -u (unbuffered) agar terminal tidak blank/stuck
            process = subprocess.Popen(
                [sys.executable, "-u", cache_file],
                stdout=sys.stdout,
                stdin=sys.stdin,
                stderr=subprocess.PIPE,
                text=True
            )
            _, stderr_output = process.communicate()

            if process.returncode != 0 and stderr_output:
                if "ModuleNotFoundError" in stderr_output:
                    match = re.search(r"No module named '(.+?)'", stderr_output)
                    if match:
                        missing_module = match.group(1)
                        self.console.print(f"\n[bold yellow]⚠ Modul kurang dideteksi:[/bold yellow] [cyan]{missing_module}[/cyan]")
                        
                        with Progress(
                            SpinnerColumn("bouncingBar", style="magenta"), 
                            TextColumn(f"[magenta]Menjalankan Auto-Install untuk [bold]{missing_module}[/bold]..."), 
                            transient=True,
                            console=self.console
                        ) as progress:
                            progress.add_task("install", start=False)
                            try:
                                subprocess.check_call([sys.executable, "-m", "pip", "install", missing_module, "-q"])
                                self.console.print(f"[bold green]✓ Modul {missing_module} berhasil diinstal! Me-restart script...[/bold green]\n")
                                time.sleep(1)
                                continue
                            except Exception as e:
                                self.console.print(f"[bold red]❌ Gagal menginstal {missing_module}: {e}[/bold red]")
                                break
                else:
                    self.console.print(f"\n[bold red]Error pada script target:[/bold red]\n{stderr_output}")
                    break
            else:
                break
                
        Prompt.ask("\n[bold white]ENTER[/bold white] untuk kembali")

    def create_repo(self):
        self.header("GITHUB REPO CREATOR")
        
        saved = self.get_saved_credentials()
        if saved and Prompt.ask(f"[bold green]➜ Gunakan akun tersimpan ({saved['username']})? (y/n)[/bold green]", choices=["y", "n"], default="y") == "y":
            username = saved['username']
            token = saved['token']
        else:
            username = Prompt.ask("\n[bold blue]👤 GitHub Username[/bold blue]").strip()
            token = Prompt.ask("[bold yellow]🔑 GitHub Token (Harus punya akses 'repo')[/bold yellow]", password=True).strip()
            if username and token: self.save_credentials(username, token)
        
        if not username or not token: return
        
        repo_name = Prompt.ask("\n[bold cyan]📁 Masukkan Nama Repository Baru[/bold cyan]").strip()
        if not repo_name: return
        
        is_private = Prompt.ask("[bold yellow]🔒 Jadikan Private? (y/n)[/bold yellow]", choices=["y", "n"], default="y") == "y"
        description = Prompt.ask("[bold white]📝 Deskripsi Repository (Opsional)[/bold white]").strip()
        
        try:
            with Progress(
                SpinnerColumn("dots", style="bold green"),
                TextColumn("[bold green]Membuat repository di GitHub...[/bold green]"),
                transient=True,
                console=self.console
            ) as progress:
                task = progress.add_task("", total=None)
                headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
                payload = {"name": repo_name, "private": is_private, "description": description}
                response = requests.post("https://api.github.com/user/repos", headers=headers, json=payload)
                
            if response.status_code == 201:
                repo_data = response.json()
                self.console.print(f"\n[bold green]✔ BERHASIL! Repository '{repo_name}' telah dibuat.[/bold green]")
                self.console.print(f"[bold cyan]🔗 URL: {repo_data['html_url']}[/bold cyan]")
                self.console.print("[italic yellow]Sekarang Anda bisa menggunakan Menu [1] Upload untuk mengisi repository ini.[/italic yellow]")
            elif response.status_code in [401, 403]:
                self.console.print(f"\n[bold red]❌ GAGAL: Token GitHub Anda tidak memiliki izin (scope 'repo').[/bold red]")
            elif response.status_code == 422:
                self.console.print(f"\n[bold red]❌ GAGAL: Repository '{repo_name}' kemungkinan sudah ada di akun Anda.[/bold red]")
            else:
                self.console.print(f"\n[bold red]❌ GAGAL: {response.status_code} - {response.text}[/bold red]")
        except Exception as e:
            self.console.print(f"\n[bold red]❌ Error Sistem: {str(e)}[/bold red]")
            
        Prompt.ask("\n[bold white]ENTER[/bold white] untuk kembali")

    def delete_repo(self):
        self.header("GITHUB REPO DELETER")
        self.console.print("[bold red]⚠️ DANGER ZONE: HAPUS REPOSITORY GITHUB ⚠️[/bold red]")
        self.console.print("[italic yellow]Fitur ini akan menghapus repository secara permanen dari akun GitHub Anda.[/italic yellow]\n")
        
        saved = self.get_saved_credentials()
        if saved and Prompt.ask(f"[bold green]➜ Gunakan akun tersimpan ({saved['username']})? (y/n)[/bold green]", choices=["y", "n"], default="y") == "y":
            username = saved['username']
            token = saved['token']
        else:
            username = Prompt.ask("[bold blue]👤 GitHub Username[/bold blue]").strip()
            token = Prompt.ask("[bold yellow]🔑 GitHub Token (Harus punya akses 'delete_repo')[/bold yellow]", password=True).strip()
            if username and token: self.save_credentials(username, token)
        
        if not username or not token: return
        
        repo = self.select_repository(token)
        if repo is None:
            Prompt.ask("\n[bold white]ENTER[/bold white] untuk kembali")
            return
            
        if not repo:
            repo_name = Prompt.ask("\n[bold cyan]📁 Masukkan Nama Repository[/bold cyan]").strip()
            if not repo_name: return
        else:
            repo_name = repo['name']
            self.console.print(f"\n[bold green]✔ Repository Terpilih:[bold white] {repo_name}[/bold white]")
            
        konfirmasi = Prompt.ask(f"\n[bold red]Apakah Anda YAKIN ingin menghapus '{username}/{repo_name}'? (y/n)[/bold red]", choices=["y", "n"])
        if konfirmasi.lower() != 'y': return
            
        try:
            with Progress(
                SpinnerColumn("dots", style="bold red"),
                TextColumn("[bold red]Menghapus repository...[/bold red]"),
                transient=True,
                console=self.console
            ) as progress:
                task = progress.add_task("", total=None)
                headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
                response = requests.delete(f"https://api.github.com/repos/{username}/{repo_name}", headers=headers)
                
            if response.status_code == 204:
                self.console.print(f"\n[bold green]✔ BERHASIL! Repository '{repo_name}' telah dihapus dari GitHub.[/bold green]")
            elif response.status_code == 404:
                self.console.print(f"\n[bold red]❌ GAGAL: Repository '{repo_name}' tidak ditemukan, atau Token Anda salah.[/bold red]")
            elif response.status_code == 403:
                self.console.print(f"\n[bold red]❌ GAGAL: Token GitHub Anda tidak memiliki izin (scope) 'delete_repo'.[/bold red]")
                self.console.print("[italic yellow]Silakan buat token baru di GitHub dan centang opsi 'delete_repo'.[/italic yellow]")
            else:
                self.console.print(f"\n[bold red]❌ GAGAL: {response.status_code} - {response.text}[/bold red]")
        except Exception as e:
            self.console.print(f"\n[bold red]❌ Error Sistem: {str(e)}[/bold red]")
            
        Prompt.ask("\n[bold white]ENTER[/bold white] untuk kembali")

    def main_loop(self):
        while True:
            self.header("GITHUB MANAGER")
            self.console.print("\n[bold cyan][1][/bold cyan] [bold green]Upload / Update Source Code[/bold green]")
            self.console.print("[bold cyan][2][/bold cyan] [bold magenta]Run Raw GitHub Script[/bold magenta]")
            self.console.print("[bold cyan][3][/bold cyan] [bold yellow]Buat Repository Baru[/bold yellow]")
            self.console.print("[bold cyan][4][/bold cyan] [bold red]Hapus Repository GitHub[/bold red]")
            self.console.print("\n[bold red][0][/bold red] [bold white]Keluar Program[/bold white]")
            
            choice = Prompt.ask("\n[bold green]➜ Pilih Opsi[/bold green]", choices=["0", "1", "2", "3", "4"])
            if choice == "1":
                self.upload_repo()
            elif choice == "2":
                self.run_raw_script()
            elif choice == "3":
                self.create_repo()
            elif choice == "4":
                self.delete_repo()
            elif choice == "0":
                self.console.print("\n[bold green]Terima kasih telah menggunakan Takaz GitHub Manager![/bold green]")
                break

if __name__ == "__main__":
    app = TakazGitHubManager()
    app.main_loop()