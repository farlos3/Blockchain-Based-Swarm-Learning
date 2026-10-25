"""The two modalities of Nguyen-Khanh et al. (2025), Sections 3.2 and 4.1, built from the releases.

Every sample is one packet seen twice:

packet branch   the packet's Tshark fields as Edge-IIoTset ships them, with the paper's 15
                columns removed, duplicates and missing rows dropped, the 7 text fields
                dummy-encoded and the rest z-scored (Ferrag et al.'s DNN preprocessing,
                which the paper lists word for word)
flow branch     the LUCID fragment the packet belongs to: its bidirectional 5-tuple flow
                within a 10 s window, the first n = 10 packets as rows of 11 features
                (Time, Packet Length, Highest Layer, IP Flags, Protocols, TCP Length, TCP
                Ack, TCP Flags, TCP Window Size, UDP Length, ICMP Type), zero-padded and
                min-max scaled by LUCID's fixed ranges (Table 3's input is 10 x 11)

Edge-IIoTset's packet rows are the paper's exactly: deduplicating the DDoS and benign rows
of DNN-EdgeIIoT-dataset.csv gives Table 7's 48,544 / 50,062 / 67,939 / 121,567. Each row is
found again in the capture it came from (by time of day and addresses, or by UDP stream for
the UDP flood, whose rows lost their timestamp in the CSV) and paired with its fragment.
CICIoMT2024 ships no packet table, so its MQTT DDoS and benign captures go through Tshark
with Edge-IIoTset's own field list, then the same preprocessing.

Hosts follow Tables 9-11: five units (HTTP+ICMP, TCP SYN, UDP, MQTT publish, MQTT connect),
each with benign traffic of its own dataset; Scenario 2 merges units 2+3 and 4+5. The
benign counts are what Tables 7 and 9-11 leave once the attacks are subtracted.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
RAW = HERE / "data" / "raw"
WORK = HERE / "data" / "work"           # tshark tables and per-capture fragments
PROCESSED = HERE / "data" / "processed"  # the paired samples every experiment reads

SEED = 42

# ---------------------------------------------------------------- sources

KAGGLE = "https://www.kaggle.com/api/v1/datasets/download"
EDGE_ZIP = RAW / "edgeiiotset-cyber-security-dataset-of-iot-iiot.zip"
EDGE_KAGGLE = "mohamedamineferrag/edgeiiotset-cyber-security-dataset-of-iot-iiot"
EDGE_DIR = "Edge-IIoTset dataset/"
EDGE_DNN = EDGE_DIR + "Selected dataset for ML and DL/DNN-EdgeIIoT-dataset.csv"
# the captures behind the rows the paper keeps: the four DDoS floods, and every normal sensor
EDGE_PCAPS = {
    "edge-ddos-http": "Attack traffic/DDoS HTTP Flood Attacks.pcap",
    "edge-ddos-icmp": "Attack traffic/DDoS ICMP Flood Attacks.pcap",
    "edge-ddos-tcp": "Attack traffic/DDoS TCP SYN Flood Attacks.pcap",
    "edge-ddos-udp": "Attack traffic/DDoS UDP Flood Attacks.pcap",
    **{f"edge-normal-{s.lower().replace('_', '-')}": f"Normal traffic/{s}/{s}.pcap" for s in (
        "Distance", "Flame_Sensor", "Heart_Rate", "IR_Receiver", "Modbus", "phValue",
        "Soil_Moisture", "Sound_Sensor", "Temperature_and_Humidity", "Water_Level")},
}
# Edge-IIoTset's frame.time is the capture's local time of day, UTC+1, without the date
EDGE_UTC_OFFSET_S = 3600

# CICIoMT2024: UNB hands it out behind a personal-details form; this is the complete release
# mirrored on Kaggle (one tar.xz, 11.0 GB), of which only the WiFi/MQTT captures below are kept
CICIOMT_ZIP = RAW / "ciciomt2024-archive.zip"
CICIOMT_KAGGLE = "cyberdeeplearning/ciciomt2024"
CICIOMT_ATTACKS = ("MQTT-DDoS-Publish_Flood", "MQTT-DDoS-Connect_Flood")
CICIOMT_KEEP = ("Benign",) + CICIOMT_ATTACKS

TSHARK = os.getenv("TSHARK") or shutil.which("tshark") or r"C:\Program Files\Wireshark\tshark.exe"

# ---------------------------------------------------------------- the paper's numbers

BENIGN = "Benign"


@dataclass(frozen=True)
class Unit:
    """One host of Scenario 3 (Table 11). Scenarios 1 and 2 are built from these."""
    name: str
    source: str                  # "edge" or "ciciomt"
    attacks: tuple[str, ...]
    benign: int                  # host total minus its attacks (Tables 7, 9-11)


# Table 7: every row of each attack the paper keeps
ATTACK_ROWS = {"DDoS_HTTP": 48_544, "DDoS_ICMP": 67_939, "DDoS_TCP": 50_062, "DDoS_UDP": 121_567,
               "MQTT-DDoS-Publish_Flood": 65_835, "MQTT-DDoS-Connect_Flood": 147_166}

UNITS = (
    Unit("http-icmp", "edge", ("DDoS_HTTP", "DDoS_ICMP"), 231_318 - 48_544 - 67_939),
    Unit("tcp-syn", "edge", ("DDoS_TCP",), 100_853 - 50_062),
    Unit("udp", "edge", ("DDoS_UDP",), 242_738 - 121_567),
    Unit("mqtt-publish", "ciciomt", ("MQTT-DDoS-Publish_Flood",), 131_683 - 65_835),
    Unit("mqtt-connect", "ciciomt", ("MQTT-DDoS-Connect_Flood",), 274_734 - 147_166),
)
assert sum(u.benign for u in UNITS) == 480_213     # Table 7's benign total

# Tables 9-11: which units each host holds
SCENARIOS = {
    1: ((0,), (1,), (2,)),
    2: ((0,), (1, 2), (3, 4)),
    3: ((0,), (1,), (2,), (3,), (4,)),
}
TEST_SHARE = 0.10     # Tables 9-11: test is 10% of a host, validation 10% of the rest
VAL_SHARE = 0.10

# ---------------------------------------------------------------- packet branch columns

# Section 3.2's removed "stream features", in the paper's order
DROPPED = ("frame.time", "ip.src_host", "ip.dst_host", "arp.src.proto_ipv4", "arp.dst.proto_ipv4",
           "http.file_data", "http.request.full_uri", "mqtt.msg", "http.request.uri.query",
           "tcp.options", "udp.port", "tcp.payload", "tcp.srcport", "tcp.dstport",
           "icmp.transmit_timestamp")
# dummy-encoded (Ferrag et al.'s preprocessing, which the paper's "dummy encoding" refers to)
CATEGORICAL = ("http.request.method", "http.referer", "http.request.version", "dns.qry.name.len",
               "mqtt.conack.flags", "mqtt.protoname", "mqtt.topic")
# the 46 columns left of Edge-IIoTset's 61, in its order
FEATURES = (
    "arp.opcode", "arp.hw.size", "icmp.checksum", "icmp.seq_le", "icmp.unused",
    "http.content_length", "http.request.method", "http.referer", "http.request.version",
    "http.response", "http.tls_port", "tcp.ack", "tcp.ack_raw", "tcp.checksum",
    "tcp.connection.fin", "tcp.connection.rst", "tcp.connection.syn", "tcp.connection.synack",
    "tcp.flags", "tcp.flags.ack", "tcp.len", "tcp.seq", "udp.stream", "udp.time_delta",
    "dns.qry.name", "dns.qry.name.len", "dns.qry.qu", "dns.qry.type", "dns.retransmission",
    "dns.retransmit_request", "dns.retransmit_request_in", "mqtt.conack.flags",
    "mqtt.conflag.cleansess", "mqtt.conflags", "mqtt.hdrflags", "mqtt.len", "mqtt.msg_decoded_as",
    "mqtt.msgtype", "mqtt.proto_len", "mqtt.protoname", "mqtt.topic", "mqtt.topic_len", "mqtt.ver",
    "mbtcp.len", "mbtcp.trans_id", "mbtcp.unit_id")
NUMERIC = tuple(f for f in FEATURES if f not in CATEGORICAL)
assert len(FEATURES) == 46 and len(NUMERIC) == 39
# FT_NONE fields print nothing with -T fields: the TCP ones are read off tcp.flags (they are
# Wireshark's names for SYN, SYN+ACK, FIN and RST), the rest are zero in every Edge row kept
FROM_FLAGS = ("tcp.connection.fin", "tcp.connection.rst", "tcp.connection.syn", "tcp.connection.synack")
ALWAYS_ZERO = ("http.tls_port", "dns.retransmit_request", "icmp.unused", "mqtt.msg_decoded_as")
TSHARK_FEATURES = tuple(f for f in FEATURES if f not in FROM_FLAGS + ALWAYS_ZERO)

# ---------------------------------------------------------------- flow branch (LUCID)

TIME_WINDOW = 10.0       # seconds (Section 3.2, after FLAD)
FLOW_PACKETS = 10        # n: Table 3's Conv2D gives 8 rows from a height-3 kernel
LUCID_PROTOCOLS = ("arp", "data", "dns", "ftp", "http", "icmp", "ip", "ssdp", "ssl", "telnet", "tcp", "udp")
# LUCID's static_min_max: every feature is divided by its fixed range (all minima are 0)
LUCID_RANGE = np.array([TIME_WINDOW, 1 << 16, 1 << 32, 1 << 16, 1 << len(LUCID_PROTOCOLS),
                        1 << 16, 1 << 32, 1 << 16, 1 << 16, 1 << 16, 1 << 8], dtype=np.float64)
FLOW_FEATURES = len(LUCID_RANGE)
LUCID_FIELDS = ("frame.time_epoch", "ip.src", "ip.dst", "ip.proto", "ip.len", "ip.flags",
                "frame.protocols", "tcp.srcport", "tcp.dstport", "tcp.len", "tcp.ack", "tcp.flags",
                "tcp.window_size_value", "udp.srcport", "udp.dstport", "udp.length", "icmp.type",
                "udp.stream")


# ================================================================ download and unpack

def download() -> None:
    """Both releases from Kaggle, anonymously, then the captures the experiment reads."""
    _fetch(EDGE_ZIP, f"{KAGGLE}/{EDGE_KAGGLE}")
    _fetch(CICIOMT_ZIP, f"{KAGGLE}/{CICIOMT_KAGGLE}")
    unpack()


def _fetch(dest: Path, url: str) -> None:
    if dest.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_name(dest.name + ".partial")
    print(f"downloading {url} -> {dest.name}", flush=True)
    with urllib.request.urlopen(url, timeout=120) as response, partial.open("wb") as out:
        expected = int(response.headers.get("Content-Length") or 0)
        shutil.copyfileobj(response, out, 1 << 22)
    if expected and partial.stat().st_size != expected:
        raise RuntimeError(f"{dest.name}: got {partial.stat().st_size:,} of {expected:,} bytes")
    with zipfile.ZipFile(partial) as z:      # a cut-off download has no central directory
        z.namelist()
    partial.rename(dest)


def unpack() -> dict[str, Path]:
    """Every capture the experiment reads, as {name: path}, unpacked once into RAW."""
    out = RAW / "pcap"
    out.mkdir(parents=True, exist_ok=True)
    found = {}
    with zipfile.ZipFile(EDGE_ZIP) as z:
        for name, member in EDGE_PCAPS.items():
            found[name] = target = out / f"{name}.pcap"
            if not target.exists():
                print(f"unpacking {member}", flush=True)
                _copy(z.open(EDGE_DIR + member), target)
    found.update(_unpack_ciciomt(out))
    return found


def _ciciomt_name(member: str) -> str | None:
    """'.../WiFI_and_MQTT/attacks/PCAP/train/MQTT-DDoS-Connect_Flood_train.pcap' -> its
    short name, or None for a capture the paper does not use."""
    path = member.replace("\\", "/")
    stem = path.rsplit("/", 1)[-1]
    if "/attacks/" not in path.lower() or "wifi" not in path.lower() or not stem.endswith(".pcap"):
        return None
    base = stem[:-len(".pcap")]
    for keep in CICIOMT_KEEP:
        if base.startswith(keep + "_") or base == keep:
            return "ciciomt-" + base.lower().replace("_", "-")
    return None


def _unpack_ciciomt(out: Path) -> dict[str, Path]:
    """The release is one tar.xz inside Kaggle's zip; it is read as a stream, once, keeping
    only the WiFi/MQTT benign and MQTT DDoS captures. The list of what was kept is written
    last, so an interrupted pass is simply run again."""
    listing = out / "ciciomt.json"
    if listing.exists():
        return {k: out / v for k, v in json.loads(listing.read_text()).items()}
    found = {}
    with zipfile.ZipFile(CICIOMT_ZIP) as z, (out / "ciciomt-members.txt").open("w") as members:
        inner = [n for n in z.namelist() if n.endswith(".tar.xz")]
        if len(inner) != 1:
            raise RuntimeError(f"{CICIOMT_ZIP.name}: expected one .tar.xz, found {z.namelist()[:5]}")
        with z.open(inner[0]) as stream, tarfile.open(fileobj=stream, mode="r|xz") as tar:
            for member in tar:
                members.write(f"{member.size}\t{member.name}\n")
                name = _ciciomt_name(member.name) if member.isfile() else None
                if name is None:
                    continue
                print(f"unpacking {member.name} ({member.size / 2**20:,.0f} MiB)", flush=True)
                _copy(tar.extractfile(member), out / f"{name}.pcap")
                found[name] = f"{name}.pcap"
    missing = [k for k in CICIOMT_KEEP if not any(n.startswith("ciciomt-" + k.lower().replace("_", "-"))
                                                  for n in found)]
    if missing:
        raise RuntimeError(f"CICIoMT2024 archive has no WiFi/MQTT capture for {missing}")
    listing.write_text(json.dumps(found, indent=1))
    return {k: out / v for k, v in found.items()}


def _copy(source, target: Path) -> None:
    partial = target.with_name(target.name + ".partial")
    with source, partial.open("wb") as out:
        shutil.copyfileobj(source, out, 1 << 22)
    partial.replace(target)


# ================================================================ tshark

# Tshark keeps state for every frame and conversation it has seen; on CICIoMT2024's MQTT
# floods (10M+ packets, a TCP connection each) that outgrows the machine. Those captures are
# read with the session reset every million packets, which restarts Wireshark's stream
# indices and relative TCP sequence numbers at each reset; Edge-IIoTset's are read whole.
RESET_EVERY = 1_000_000


def tshark(pcap: Path, fields: tuple[str, ...]) -> Path:
    """The capture's fields, one row per packet in capture order, as a cached TSV. Rows are
    identified by their position: frame numbers restart where the session is reset."""
    target = WORK / "tshark" / f"{pcap.stem}.tsv"
    if target.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".partial")
    command = [TSHARK, "-n", "-r", str(pcap), "-T", "fields", "-E", "header=y", "-E", "separator=/t",
               "-E", "occurrence=f", "-E", "quote=n"]
    if pcap.stem.startswith("ciciomt-"):
        command += ["-M", str(RESET_EVERY)]
    for f in fields:
        command += ["-e", f]
    with partial.open("wb") as out:
        subprocess.run(command, stdout=out, stderr=subprocess.DEVNULL, check=True)
    partial.replace(target)
    return target


def read_tsv(path: Path, columns: list[str] | None = None, chunk: int = 1_000_000):
    """The TSV in chunks of strings, empty where Tshark printed nothing; the index runs on
    across chunks, so it is the packet's position in the capture."""
    return pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False, usecols=columns,
                       quoting=csv.QUOTE_NONE, chunksize=chunk, on_bad_lines="error")


# ================================================================ LUCID fragments

def _ipv4(s: pd.Series) -> np.ndarray:
    parts = s.str.split(".", n=3, expand=True).to_numpy(np.uint32)
    return (parts[:, 0] << 24) | (parts[:, 1] << 16) | (parts[:, 2] << 8) | parts[:, 3]


def _int(s: pd.Series, base: int = 10) -> np.ndarray:
    if base == 16:
        return s.map(lambda v: int(v, 16) if v else 0).to_numpy(np.int64)
    return pd.to_numeric(s.replace("", "0")).to_numpy(np.int64)


_HASHES: dict[str, tuple[int, int]] = {}


def _layer_codes(protocols: str) -> tuple[int, int]:
    """LUCID's highest-layer hash and protocol bitmask for one frame.protocols string.

    pyshark's highest_layer is the last dissected protocol, upper-cased; 'ethertype' is a
    field of eth there, not a layer.
    """
    if protocols not in _HASHES:
        layers = [p for p in protocols.split(":") if p != "ethertype"]
        top = layers[-1].upper() if layers else ""
        present = set(layers)
        mask = sum(1 << i for i, p in enumerate(LUCID_PROTOCOLS) if p in present)
        _HASHES[protocols] = (int(hashlib.sha256(top.encode()).hexdigest(), 16) % 10**8, mask)
    return _HASHES[protocols]


def lucid_packets(tsv: Path) -> pd.DataFrame:
    """LUCID's parse_packet over a whole capture: one row per IPv4 packet (others carry no
    flow), its 11 features already scaled by LUCID's fixed ranges (time is filled in by
    `fragments`), its flow key and the identity fields used to find it again."""
    rows = []
    for c in read_tsv(tsv, list(LUCID_FIELDS)):
        c = c[c["ip.src"] != ""]
        if c.empty:
            continue
        sec, frac = c["frame.time_epoch"].str.split(".", n=1, expand=True).T.values
        us = pd.Series(sec).astype(np.int64).to_numpy() * 1_000_000 +             pd.Series(frac).str[:6].str.ljust(6, "0").astype(np.int64).to_numpy()
        proto = _int(c["ip.proto"])
        tcp = (proto == 6) & (c["tcp.srcport"] != "").to_numpy()
        udp = (proto == 17) & (c["udp.srcport"] != "").to_numpy()
        icmp = (proto == 1) & ~tcp & ~udp
        codes = np.array([_layer_codes(p) for p in c["frame.protocols"]], dtype=np.int64).reshape(-1, 2)
        feats = np.zeros((len(c), FLOW_FEATURES), dtype=np.float64)
        feats[:, 1] = _int(c["ip.len"])
        feats[:, 2] = codes[:, 0]
        feats[:, 3] = _int(c["ip.flags"], 16) << 13       # LUCID read the 16-bit flags+offset word
        feats[:, 4] = codes[:, 1]
        feats[:, 5] = np.where(tcp, _int(c["tcp.len"]), 0)
        feats[:, 6] = np.where(tcp, _int(c["tcp.ack"]), 0)
        feats[:, 7] = np.where(tcp, _int(c["tcp.flags"], 16), 0)
        feats[:, 8] = np.where(tcp, _int(c["tcp.window_size_value"]), 0)
        feats[:, 9] = np.where(udp, _int(c["udp.length"]), 0)
        feats[:, 10] = np.where(icmp, _int(c["icmp.type"]), 0)
        feats = (feats / LUCID_RANGE).astype(np.float32)
        sport = np.where(tcp, _int(c["tcp.srcport"]), np.where(udp, _int(c["udp.srcport"]), 0))
        dport = np.where(tcp, _int(c["tcp.dstport"]), np.where(udp, _int(c["udp.dstport"]), 0))
        frame = pd.DataFrame({
            "frame": c.index.to_numpy(np.int64), "us": us,
            "src": _ipv4(c["ip.src"]), "dst": _ipv4(c["ip.dst"]),
            "sport": sport.astype(np.int32), "dport": dport.astype(np.int32),
            # LUCID keys anything that is not TCP, UDP or ICMP with protocol 0 and no ports
            "proto": np.where(tcp | udp | icmp, proto, 0).astype(np.int16),
            "udp_stream": np.where(udp, _int(c["udp.stream"]), -1),
            **{f"f{i}": feats[:, i] for i in range(FLOW_FEATURES)},
        })
        rows.append(frame)
    return pd.concat(rows, ignore_index=True)


def fragments(packets: pd.DataFrame) -> pd.DataFrame:
    """LUCID's process_pcap: windows, bidirectional flows, and each flow's first n packets.

    A window opens at the first packet and the next one at the first packet more than
    TIME_WINDOW later, for the whole capture at once (not per flow). Within a window a flow
    keeps its first FLOW_PACKETS packets; later ones are not stored. Time (f0) becomes the
    offset from the earliest stored packet of the fragment, scaled by the window. Adds the
    columns `fragment` and `pos` (place within it) to `packets` in place.
    """
    us = packets["us"].to_numpy()
    t = us / 1e6
    reach = np.maximum.accumulate(t)            # first packet past start + window, in file order
    window = np.empty(len(t), dtype=np.int64)
    start, w = 0, 0
    while start < len(t):
        end = int(np.searchsorted(reach, t[start] + TIME_WINDOW, side="right"))
        window[start:end] = w
        start, w = end, w + 1
    a = packets["src"].to_numpy(np.int64) << 16 | packets["sport"].to_numpy(np.int64)
    b = packets["dst"].to_numpy(np.int64) << 16 | packets["dport"].to_numpy(np.int64)
    keys = pd.DataFrame({"lo": np.minimum(a, b), "hi": np.maximum(a, b),
                         "proto": packets["proto"].to_numpy(), "window": window})
    fragment = keys.groupby(["lo", "hi", "proto", "window"], sort=False).ngroup().to_numpy()
    del keys, a, b, window
    packets["fragment"] = fragment
    packets["pos"] = packets.groupby("fragment").cumcount().to_numpy(np.int32)
    first = pd.Series(np.where(packets["pos"].to_numpy() < FLOW_PACKETS, us, np.iinfo(np.int64).max))
    first = first.groupby(fragment).transform("min").to_numpy()
    packets["f0"] = ((us - first) / 1e6 / TIME_WINDOW).astype(np.float32)
    return packets


def capture_packets(name: str, pcap: Path, fields: tuple[str, ...], columns: list[str] | None = None) -> pd.DataFrame:
    """A capture's IPv4 packets with their fragment (only `columns` of it), cached as parquet."""
    target = WORK / "packets" / f"{name}.parquet"
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        fragments(lucid_packets(tshark(pcap, fields))).to_parquet(target, index=False)
    return pd.read_parquet(target, columns=columns)


def flow_matrices(table: pd.DataFrame, wanted: np.ndarray) -> np.ndarray:
    """The (len(wanted), FLOW_PACKETS, FLOW_FEATURES) arrays of the given fragments of one
    capture, zero-padded below their last stored packet."""
    out = np.zeros((len(wanted), FLOW_PACKETS, FLOW_FEATURES), dtype=np.float32)
    where = pd.Series(np.arange(len(wanted)), index=wanted)
    kept = table[(table["pos"] < FLOW_PACKETS) & table["fragment"].isin(wanted)]
    rows = where.loc[kept["fragment"].to_numpy()].to_numpy()
    out[rows, kept["pos"].to_numpy()] = kept[[f"f{i}" for i in range(FLOW_FEATURES)]].to_numpy()
    return out


# ================================================================ Edge-IIoTset

EDGE_TYPES = ("Normal", "DDoS_HTTP", "DDoS_ICMP", "DDoS_TCP", "DDoS_UDP")


def edge_rows() -> pd.DataFrame:
    """Ferrag et al.'s preprocessing of DNN-EdgeIIoT-dataset.csv for the DDoS and normal rows:
    the 15 columns out, rows with a missing value out, then duplicates out (first kept).
    The removed columns survive only as the identity used to find each row's capture."""
    with zipfile.ZipFile(EDGE_ZIP) as z, z.open(EDGE_DNN) as f:
        df = pd.read_csv(f, dtype=str)
    df = df[df["Attack_type"].isin(EDGE_TYPES)]
    df = df[~df[list(FEATURES)].isna().any(axis=1)]
    df = df.drop_duplicates(subset=list(FEATURES) + ["Attack_label", "Attack_type"], keep="first")
    identity = ["frame.time", "ip.src_host", "ip.dst_host", "tcp.srcport"]     # udp.stream is a feature
    return df[[*identity, "Attack_type", *FEATURES]].reset_index(drop=True)


def _ip_or_none(s: pd.Series) -> pd.Series:
    ok = s.str.fullmatch(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", na=False)
    out = pd.Series(np.full(len(s), -1, dtype=np.int64), index=s.index)
    out[ok] = _ipv4(s[ok]).astype(np.int64)
    return out


def edge_keys(rows: pd.DataFrame) -> pd.DataFrame:
    """How each row is found in a capture.

    Most rows keep '2021 HH:MM:SS.fffffffff' (the date was lost to a comma) and their
    addresses: time of day to the microsecond plus both addresses pins one packet. The UDP
    flood's rows lost frame.time altogether and are shifted, in two ways:
      'frame.time' holds the (spoofed) source address, 'tcp.srcport' the UDP source port and
      'udp.stream' Wireshark's stream index — those three pin the packet;
      'frame.time' holds the victim, 'ip.src_host' the source and 'udp.stream' the UDP source
      port ('tcp.srcport' is 0) — source address and port pin it.
    Rows without an IPv4 address (IPv6, ARP) have no LUCID flow and stay unmatched.
    """
    tod = rows["frame.time"].str.extract(r"^\s*\d{4} (\d\d):(\d\d):(\d\d)\.(\d{6})\d*\s*$")
    has_time = tod[0].notna()
    us = pd.Series(np.full(len(rows), -1, dtype=np.int64), index=rows.index)
    t = tod[has_time].astype(np.int64)
    us[has_time] = ((t[0] * 60 + t[1]) * 60 + t[2]) * 1_000_000 + t[3]
    lost = ~has_time & rows["Attack_type"].eq("DDoS_UDP")
    srcport = pd.to_numeric(rows["tcp.srcport"], errors="coerce").fillna(-1).astype(np.int64)
    column = pd.to_numeric(rows["udp.stream"], errors="coerce").fillna(-1).astype(np.int64)
    shifted, moved = lost & (srcport > 0), lost & (srcport == 0)
    keys = pd.DataFrame({
        "tod": us,
        "src": np.where(shifted, _ip_or_none(rows["frame.time"]), _ip_or_none(rows["ip.src_host"])),
        "dst": np.where(has_time, _ip_or_none(rows["ip.dst_host"]), -1),
        "sport": np.where(shifted, srcport, np.where(moved, column, -1)),
        "udp_stream": np.where(shifted, column, -1),
    }, index=rows.index)
    ip = (keys["src"] > 0) & ((keys["dst"] > 0) | ~has_time)       # '0' is no address
    keys["by"] = np.select([has_time & ip, shifted & ip, moved & ip], ["time", "udp", "udp-port"], "none")
    return keys


def match_edge(keys: pd.DataFrame, name: str, table: pd.DataFrame) -> pd.DataFrame:
    """Rows of `keys` found in this capture: row index -> (capture, fragment)."""
    found = []
    by_time = keys[keys["by"] == "time"]
    if len(by_time):
        tod = (table["us"] // 1_000_000 + EDGE_UTC_OFFSET_S) % 86_400 * 1_000_000 + table["us"] % 1_000_000
        packets = pd.DataFrame({"tod": tod, "src": table["src"].astype(np.int64),
                                "dst": table["dst"].astype(np.int64), "fragment": table["fragment"]})
        packets = packets.drop_duplicates(["tod", "src", "dst"], keep="first")
        found.append(by_time.reset_index().merge(packets, on=["tod", "src", "dst"])[["index", "fragment"]])
    udp = table.loc[table["udp_stream"] >= 0, ["src", "sport", "udp_stream", "fragment"]].astype(np.int64)
    for by, on in (("udp", ["src", "sport", "udp_stream"]), ("udp-port", ["src", "sport"])):
        wanted = keys[keys["by"] == by]
        if len(wanted):
            packets = udp.drop_duplicates(on, keep="first")[on + ["fragment"]]
            found.append(wanted.reset_index()[["index", *on]].merge(packets, on=on)[["index", "fragment"]])
    out = pd.concat(found, ignore_index=True) if found else pd.DataFrame(columns=["index", "fragment"])
    return out.assign(capture=name)


# ================================================================ CICIoMT2024

def _number(v: str) -> float:
    """A Tshark value the way Edge-IIoTset's numeric columns hold it."""
    if not v:
        return 0.0
    if v.startswith("0x"):
        return float(int(v, 16))
    if v in ("True", "False"):
        return float(v == "True")
    try:
        return float(v)
    except ValueError:
        return 0.0          # a text value in a column Edge-IIoTset keeps as a number


def edge_format(raw: pd.DataFrame) -> pd.DataFrame:
    """Tshark output in Edge-IIoTset's representation of the 46 packet features."""
    out = pd.DataFrame(index=raw.index)
    flags = raw["tcp.flags"].map(lambda v: int(v, 16) if v else 0)
    syn, ack, fin, rst = (flags & 2) > 0, (flags & 16) > 0, (flags & 1) > 0, (flags & 4) > 0
    derived = {"tcp.connection.fin": fin, "tcp.connection.rst": rst,
               "tcp.connection.syn": syn & ~ack, "tcp.connection.synack": syn & ack}
    for f in FEATURES:
        if f in derived:
            out[f] = derived[f].astype(np.float64)
        elif f in ALWAYS_ZERO:
            out[f] = 0.0
        elif f in CATEGORICAL:
            col = raw[f]
            if f == "mqtt.conack.flags":         # Edge-IIoTset writes it as 0x%08x
                col = col.map(lambda v: f"0x{int(v, 16):08x}" if v.startswith("0x") else v)
            out[f] = col.replace("", "0")
        else:
            out[f] = raw[f].map(_number)
    return out


def ciciomt_class(name: str) -> str:
    """The traffic a CICIoMT2024 capture holds: UNB labels by file."""
    return next((a for a in CICIOMT_ATTACKS if name.startswith("ciciomt-" + a.lower().replace("_", "-"))), BENIGN)


def ciciomt_rows(names: list[str], pcaps: dict[str, Path], wanted: dict[str, int],
                 rng: np.random.Generator) -> tuple[pd.DataFrame, dict]:
    """Per traffic type: every IPv4 packet of its captures (train before test), duplicates
    out (first kept), then wanted[type] of them drawn at random, in Edge-IIoTset's
    representation and with their fragment.

    The captures hold millions of packets, so duplicates are found by hashing the raw
    Tshark fields (a one-to-one stand-in for the formatted values), and only the drawn
    rows are parsed.
    """
    fields = tuple(dict.fromkeys(LUCID_FIELDS + TSHARK_FEATURES))
    report, out = {}, []
    for kind in sorted({ciciomt_class(n) for n in names}):
        members = sorted((n for n in names if ciciomt_class(n) == kind), key=lambda n: (n.endswith("test"), n))
        seen = []
        for k, name in enumerate(members):
            for raw in read_tsv(tshark(pcaps[name], fields), ["ip.src", *TSHARK_FEATURES]):
                raw = raw[raw["ip.src"] != ""]
                seen.append(pd.DataFrame({
                    "capture": k, "frame": raw.index.to_numpy(np.int64),
                    "hash": pd.util.hash_pandas_object(raw[list(TSHARK_FEATURES)], index=False).to_numpy()}))
        seen = pd.concat(seen, ignore_index=True)
        unique = seen.drop_duplicates("hash", keep="first")
        take = unique.iloc[np.sort(rng.choice(len(unique), size=min(wanted[kind], len(unique)), replace=False))]
        report[kind] = {"ipv4_packets": len(seen), "after_dedup": len(unique), "drawn": len(take)}
        for k, name in enumerate(members):
            frames = take.loc[take["capture"] == k, "frame"].to_numpy()
            fragment = capture_packets(name, pcaps[name], fields, ["frame", "fragment"]).set_index("frame")["fragment"]
            for raw in read_tsv(tshark(pcaps[name], fields), list(TSHARK_FEATURES)):
                raw = raw[np.isin(raw.index.to_numpy(), frames)]
                if raw.empty:
                    continue
                part = edge_format(raw)
                part["fragment"] = fragment.loc[raw.index.to_numpy()].to_numpy()
                part["capture"] = name
                part["Attack_type"] = kind
                out.append(part)
    rows = pd.concat(out, ignore_index=True)
    for f in NUMERIC:
        rows[f] = rows[f].astype(np.float64)
    return rows, report


# ================================================================ samples

def prepare(workers: int = 6) -> Path:
    """Pair every kept packet with its fragment and draw the hosts' rows, once.

    Writes PROCESSED/samples.parquet (one row per sample: unit, split, label, the 46 packet
    features, an index into flows.npy) and PROCESSED/flows.npy (N, 10, 11).
    """
    samples_path, flows_path = PROCESSED / "samples.parquet", PROCESSED / "flows.npy"
    if samples_path.exists() and flows_path.exists():
        return samples_path
    PROCESSED.mkdir(parents=True, exist_ok=True)
    pcaps = unpack()
    rng = np.random.default_rng(SEED)
    report: dict = {}

    # tshark is the slow part and runs one process per capture
    edge_names = [n for n in pcaps if n.startswith("edge-")]
    cic_names = [n for n in pcaps if n.startswith("ciciomt-")]
    cic_fields = tuple(dict.fromkeys(LUCID_FIELDS + TSHARK_FEATURES))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(lambda n: tshark(pcaps[n], LUCID_FIELDS), edge_names))
        list(pool.map(lambda n: tshark(pcaps[n], cic_fields), cic_names))

    # ---- Edge-IIoTset: the paper's rows, each found again in its capture
    rows = edge_rows()
    report["edge_rows_after_dedup"] = rows["Attack_type"].value_counts().to_dict()
    keys = edge_keys(rows)
    hits = []
    for name in edge_names:
        table = capture_packets(name, pcaps[name], LUCID_FIELDS,
                                ["us", "src", "dst", "sport", "udp_stream", "fragment"])
        hits.append(match_edge(keys, name, table))
        print(f"{name}: {len(table):,} IPv4 packets, {len(hits[-1]):,} rows found", flush=True)
    hits = pd.concat(hits, ignore_index=True).drop_duplicates("index", keep="first").set_index("index")
    rows = rows.join(hits, how="inner")
    report["edge_rows_paired"] = rows["Attack_type"].value_counts().to_dict()
    edge = rows[["Attack_type", "capture", "fragment", *FEATURES]].copy()
    edge["Attack_type"] = edge["Attack_type"].replace("Normal", BENIGN)
    edge["source"] = "edge"
    for f in NUMERIC:
        edge[f] = edge[f].astype(np.float64)
    del rows, keys, hits

    # ---- CICIoMT2024: its captures' packets, deduplicated the same way, drawn to the paper's counts
    wanted = {a: ATTACK_ROWS[a] for a in CICIOMT_ATTACKS}
    wanted[BENIGN] = sum(u.benign for u in UNITS if u.source == "ciciomt")
    for name in cic_names:
        capture_packets(name, pcaps[name], cic_fields, ["frame"])
    cic, report["ciciomt"] = ciciomt_rows(cic_names, pcaps, wanted, rng)
    cic["source"] = "ciciomt"

    # ---- the hosts: every attack row of Table 7 (or all there are), benign drawn per source
    pools = {s: d.sample(frac=1.0, random_state=SEED).reset_index(drop=True)
             for s, d in (("edge", edge), ("ciciomt", cic))}
    taken = {"edge": 0, "ciciomt": 0}
    benign = {s: p[p["Attack_type"] == BENIGN].reset_index(drop=True) for s, p in pools.items()}
    drawn = []
    for i, unit in enumerate(UNITS):
        pool = pools[unit.source]
        parts = [pool[pool["Attack_type"] == a].head(ATTACK_ROWS[a]) for a in unit.attacks]
        b = benign[unit.source].iloc[taken[unit.source]:taken[unit.source] + unit.benign]
        taken[unit.source] += len(b)
        if len(b) < unit.benign:
            print(f"warning: {unit.name} has {len(b):,} of {unit.benign:,} benign rows", flush=True)
        part = pd.concat(parts + [b], ignore_index=True).assign(unit=i)
        part["split"] = _split(part["Attack_type"].to_numpy(), rng)
        drawn.append(part)
    samples = pd.concat(drawn, ignore_index=True)
    samples["label"] = (samples["Attack_type"] != BENIGN).astype(np.int8)
    report["units"] = {u.name: samples[samples["unit"] == i].groupby(["split", "Attack_type"]).size()
                       .unstack(fill_value=0).to_dict() for i, u in enumerate(UNITS)}

    # ---- one flow matrix per sample, read from the capture its packet came from
    flows = np.zeros((len(samples), FLOW_PACKETS, FLOW_FEATURES), dtype=np.float32)
    for name, group in samples.groupby("capture"):
        table = pd.read_parquet(WORK / "packets" / f"{name}.parquet",
                                columns=["fragment", "pos", *[f"f{i}" for i in range(FLOW_FEATURES)]])
        wanted = group["fragment"].to_numpy(np.int64)
        unique, inverse = np.unique(wanted, return_inverse=True)
        flows[group.index.to_numpy()] = flow_matrices(table, unique)[inverse]
    samples["flow"] = np.arange(len(samples))
    np.save(flows_path, flows)
    samples.to_parquet(samples_path, index=False)
    (PROCESSED / "prepare.json").write_text(json.dumps(report, indent=1, default=str))
    return samples_path


def _split(types: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """test = 10% of the host, val = 10% of the rest, train the remaining 81%, per class."""
    out = np.full(len(types), "train", dtype=object)
    for t in np.unique(types):
        idx = rng.permutation(np.flatnonzero(types == t))
        n_test = round(len(idx) * TEST_SHARE)
        n_val = round((len(idx) - n_test) * VAL_SHARE)
        out[idx[:n_test]] = "test"
        out[idx[n_test:n_test + n_val]] = "val"
    return out


# ================================================================ what the experiments read

@dataclass
class Split:
    packet: np.ndarray       # (n, F) float32, z-scored
    flow: np.ndarray         # (n, 10, 11) float32, LUCID-scaled
    y: np.ndarray            # (n,) float32, 1 = attack
    types: np.ndarray        # (n,) attack type, for per-class reading of errors


@dataclass
class Host:
    name: str
    train: Split
    val: Split
    test: Split


@dataclass
class Scenario:
    number: int
    hosts: list[Host]
    features: list[str]

    @property
    def n_features(self) -> int:
        return len(self.features)

    def stacked(self, split: str) -> Split:
        parts = [getattr(h, split) for h in self.hosts]
        return Split(*(np.concatenate([getattr(p, f) for p in parts]) for f in ("packet", "flow", "y", "types")))


def load(number: int) -> Scenario:
    """Scenario `number`'s hosts (Tables 9-11).

    Dummy columns are the categories occurring in the scenario's rows; the z-score uses the
    scenario's training rows (the paper encodes and scales the dataset before splitting it
    into hosts). Nodes would agree on these statistics by sharing counts, means and
    variances, never rows.
    """
    samples = pd.read_parquet(prepare())
    flows = np.load(PROCESSED / "flows.npy", mmap_mode="r")
    units = sorted({u for host in SCENARIOS[number] for u in host})
    rows = samples[samples["unit"].isin(units)]
    encoded = pd.get_dummies(rows[list(FEATURES)], columns=list(CATEGORICAL), prefix_sep="-", dtype=np.float32)
    train = rows["split"].eq("train").to_numpy()
    X = encoded.to_numpy(np.float64)
    mean, std = X[train].mean(axis=0), X[train].std(axis=0)
    X = ((X - mean) / np.where(std > 0, std, 1.0)).astype(np.float32)

    hosts = []
    for members in SCENARIOS[number]:
        in_host = rows["unit"].isin(members).to_numpy()
        splits = {}
        for split in ("train", "val", "test"):
            mask = in_host & rows["split"].eq(split).to_numpy()
            part = rows[mask]
            splits[split] = Split(X[mask], np.ascontiguousarray(flows[part["flow"].to_numpy()]),
                                  part["label"].to_numpy(np.float32), part["Attack_type"].to_numpy(str))
        hosts.append(Host("+".join(UNITS[u].name for u in members), **splits))
    return Scenario(number, hosts, list(encoded.columns))


if __name__ == "__main__":
    if sys.argv[1:] == ["download"]:
        download()
    elif sys.argv[1:] == ["prepare"]:
        prepare()
        print((PROCESSED / "prepare.json").read_text())
    else:
        sys.exit("usage: data.py download | prepare")
