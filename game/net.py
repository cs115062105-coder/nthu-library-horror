"""兩人連線：一台開房間（host），另一台加入（client），兩台連同一個 Wi-Fi 或手機熱點就好。

· 用 TCP 傳一行一行的 JSON，收資料放在背景執行緒，遊戲每一幀從 poll() 拿，不會因為網路慢而卡畫面。
· 開房間的那台每秒用 UDP 廣播一次「這裡有房間」，加入的那台按「自動找房間」就收得到，不用打 IP。
  （有些校園 Wi-Fi 會擋廣播，這時候改用 IP 加入。）
"""
import json
import queue
import socket
import threading
import time

PORT = 50517          # 遊戲連線
BEACON = 50518        # 找房間的廣播
MAGIC = b"TOUJUAN1"


def local_ip():
    """這台電腦在區網裡的 IP（給對方加入用）。不會真的送封包出去。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class Net:
    def __init__(self):
        self.inbox = queue.Queue()
        self.sock = None
        self.server = None
        self.connected = False
        self.closed = False
        self.is_host = False
        self.lock = threading.Lock()

    # ---------- 開房間 ----------
    def host(self):
        self.is_host = True
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(("", PORT))
        self.server.listen(1)
        self.server.settimeout(0.5)
        threading.Thread(target=self._accept, daemon=True).start()
        threading.Thread(target=self._beacon, daemon=True).start()

    def _accept(self):
        while not self.closed and not self.connected:
            try:
                conn, addr = self.server.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            self._attach(conn)
            self.inbox.put({"t": "joined", "ip": addr[0]})
            return

    def _beacon(self):
        b = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        b.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while not self.closed and not self.connected:
            for addr in ("<broadcast>", "255.255.255.255"):
                try:
                    b.sendto(MAGIC, (addr, BEACON))
                    break
                except OSError:
                    continue
            time.sleep(0.8)
        b.close()

    # ---------- 加入 ----------
    def join(self, ip):
        """在背景連線，連上或失敗都會放一則訊息到 inbox。"""
        def go():
            try:
                s = socket.create_connection((ip, PORT), timeout=4)
            except OSError as e:
                self.inbox.put({"t": "fail", "why": f"連不上 {ip}（{e.strerror or e}）"})
                return
            self._attach(s)
            self.inbox.put({"t": "connected", "ip": ip})
        threading.Thread(target=go, daemon=True).start()

    def search(self, seconds=6):
        """聽開房間那台的廣播，找到就直接加入。"""
        def go():
            u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            u.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if hasattr(socket, "SO_REUSEPORT"):
                try:
                    u.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                except OSError:
                    pass
            try:
                u.bind(("", BEACON))
            except OSError as e:
                self.inbox.put({"t": "fail", "why": f"沒辦法找房間（{e.strerror or e}），請改用 IP 加入"})
                return
            u.settimeout(0.5)
            end = time.time() + seconds
            while time.time() < end and not self.closed:
                try:
                    data, addr = u.recvfrom(64)
                except socket.timeout:
                    continue
                except OSError:
                    break
                if data == MAGIC:
                    u.close()
                    self.inbox.put({"t": "found", "ip": addr[0]})
                    self.join(addr[0])
                    return
            u.close()
            if not self.closed:
                self.inbox.put({"t": "fail", "why": "找不到房間。確定對方按了「開房間」、兩台連同一個網路，或改用 IP 加入"})
        threading.Thread(target=go, daemon=True).start()

    # ---------- 收送 ----------
    def _attach(self, s):
        s.settimeout(None)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)    # 小封包馬上送，不要等
        self.sock = s
        self.connected = True
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        buf = b""
        while not self.closed:
            try:
                data = self.sock.recv(65536)
            except OSError:
                data = b""
            if not data:
                if not self.closed:
                    self.inbox.put({"t": "lost"})
                self.connected = False
                return
            buf += data
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                try:
                    self.inbox.put(json.loads(line))
                except ValueError:
                    pass

    def send(self, msg):
        if not self.connected:
            return
        data = (json.dumps(msg, separators=(",", ":")) + "\n").encode()
        try:
            with self.lock:
                self.sock.sendall(data)
        except OSError:
            self.connected = False
            self.inbox.put({"t": "lost"})

    def poll(self):
        out = []
        while True:
            try:
                out.append(self.inbox.get_nowait())
            except queue.Empty:
                return out

    def close(self):
        if self.connected:
            self.send({"t": "bye"})
        self.closed = True
        self.connected = False
        for s in (self.sock, self.server):
            if s:
                try:
                    s.close()
                except OSError:
                    pass
