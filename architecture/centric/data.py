"""Datasets, client partitions and per-client preprocessing, following Bilal et al. (2026).

What is taken from the paper, and where:

    clients, sizes, benign share, class coverage   Fig. 3 (and Table 2)
    seeds                                          Fig. 3: global 42, Edge 1729, CIC 2023, TII 1103
    label families                                 Table 1 and Section 3 (Edge 5+1, CIC 7+1, TII 4+1)
    common 4-class map                             Section 4.1: Benign, DoS/DDoS, Recon/InfoGather, BruteForce
    features                                       numeric only, no IP or port identifiers
    scaling                                        z-score per client, fitted on that client's training split
    validation split                               stratified 90/10 of the client's data (Algorithm 3)
    no re-balancing, no augmentation               Section 4.3

What cannot be taken from the paper, and what replaces it (see README):

    row counts       the paper trains on 21M / 46M / 8.7M flows. Training on every row is
                     out of reach here, so each scenario draws a row budget (--rows) with
                     the Fig. 3 proportions and the release's own class shares (see Pool)
    TII benign       Fig. 3's 0.85% would take ~74,000 benign flows; the release has 1,301,
                     so TII's clients keep the release's share (TII.benign_share)
    device groups    the public CSVs carry no device identifier, so the Fig. 3 class coverage
                     and client sizes define the partition rather than a device column
    Table 3          the 40 CICFlowMeter features exist only in TII-SSRC-23; Edge-IIoTset ships
                     packet fields and CIC-IoT2023 its own window features. The shared schema
                     is the semantic intersection of all three (HARMONIZED below)
    test split       not given; 20% of each client, stratified
"""

from __future__ import annotations

import argparse
import json
import shutil
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from sklearn.model_selection import train_test_split

HERE = Path(__file__).resolve().parent
RAW = HERE / "data" / "raw"

GLOBAL_SEED = 42
TEST_SHARE = 0.20
VAL_SHARE = 0.10
MIN_CLASS_ROWS = 10   # fewest rows of a class a client is given (see allocate)

BENIGN = "Benign"
COMMON_CLASSES = (BENIGN, "DoS", "Recon", "BruteForce")

# The semantic intersection of the three schemas: the share of packets carrying each TCP
# flag, and which transport the traffic used. A packet-level row (Edge) gives 0 or 1, a
# window (CIC) or a flow (TII) gives the fraction, so the same column means the same thing.
HARMONIZED = ("fin", "syn", "rst", "psh", "ack", "ece", "cwr", "tcp", "udp", "icmp")
TCP_FLAG_BITS = {"fin": 1, "syn": 2, "rst": 4, "psh": 8, "ack": 16, "ece": 64, "cwr": 128}


# ---------- what the paper specifies per dataset ----------

@dataclass(frozen=True)
class ClientSpec:
    flows: float              # Fig. 3 "Total flows", in millions: only the ratio is used
    families: tuple[str, ...]  # attack families this client holds; Benign is always present
    key: str                  # Fig. 3 stratification key, kept for the report


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    seed: int
    benign_share: float | None  # Fig. 3's share per client; None: the release's own share
    families: tuple[str, ...]   # class order of the in-domain task, Benign first
    clients: tuple[ClientSpec, ...]
    flows_millions: float       # Table 1 size, used to weight the combined federation


EDGE = DatasetSpec(
    name="edge", seed=1729, benign_share=0.54, flows_millions=21.0,
    families=(BENIGN, "DoS/DDoS", "InfoGather", "Injection", "MITM", "Malware"),
    clients=(
        ClientSpec(3.8, ("DoS/DDoS", "InfoGather"), "video-surveillance"),
        ClientSpec(3.6, ("DoS/DDoS", "MITM"), "smart-home"),
        ClientSpec(3.4, ("Injection", "InfoGather"), "industrial-sensors"),
        ClientSpec(3.2, ("Malware", "DoS/DDoS"), "SCADA/PLC"),
        ClientSpec(3.5, ("DoS/DDoS", "Injection", "InfoGather"), "smart-lighting"),
        ClientSpec(3.5, ("DoS/DDoS", "Malware", "MITM"), "mixed-IoT"),
    ),
)

_CIC_ALL = ("DDoS", "DoS", "Mirai", "Spoofing", "Recon", "Web", "BruteForce")
_CIC_NO_BF = tuple(f for f in _CIC_ALL if f != "BruteForce")
_CIC_NO_WEB_BF = tuple(f for f in _CIC_NO_BF if f != "Web")
CIC = DatasetSpec(
    name="cic", seed=2023, benign_share=0.023, flows_millions=46.0,
    families=(BENIGN,) + _CIC_ALL,
    clients=(
        ClientSpec(5.5, _CIC_ALL, "G1 cameras"),
        ClientSpec(5.2, _CIC_ALL, "G2 sensors"),
        ClientSpec(4.9, _CIC_ALL, "G3 hubs"),
        ClientSpec(4.8, _CIC_ALL, "G4 appliances"),
        ClientSpec(4.7, _CIC_ALL, "G5 routers"),
        ClientSpec(4.6, _CIC_NO_BF, "G6 wearables"),
        ClientSpec(4.5, _CIC_ALL, "G7 meters"),
        ClientSpec(4.4, _CIC_NO_BF, "G8 speakers"),
        ClientSpec(3.9, _CIC_ALL, "G9 lighting"),
        ClientSpec(3.5, _CIC_NO_WEB_BF, "G10 mixed"),
    ),
)

_TII_ALL = ("DoS", "InfoGather", "Mirai", "BruteForce")
# Fig. 3 gives TII clients 0.85% benign, which would take ~74,000 benign flows. The release
# has 1,301 of 8,656,767 (0.015%); its attack counts match the paper's Fig. 2c. The paper
# also calls this partition a stratified random one, so the clients keep the release's mix.
TII = DatasetSpec(
    name="tii", seed=1103, benign_share=None, flows_millions=8.7,
    families=(BENIGN,) + _TII_ALL,
    clients=tuple(ClientSpec(m, _TII_ALL, "stratified random flows")
                  for m in (1.8, 1.8, 1.7, 1.7, 1.7)),
)

DATASETS = {spec.name: spec for spec in (EDGE, CIC, TII)}


# ---------- raw sources ----------

# Every dataset's complete release, which is what the paper trains on — there is no reduced
# or mirrored stand-in: a run either has the real data or it does not run.
#
# CIC-IoT2023 as Neto et al. first released it: 46,686,579 rows and 46 features, the counts
# the paper gives. UNB's page now hands out a later MERGED_CSV release with 39 features and
# 45.0M rows instead, so this copy of the original, kept on Hugging Face, is the one that
# matches the paper. Its two files together are the whole release.
HF_FILES = {
    "cic-neto/train.parquet":
        ("lacg030175/CIC-IoT-2023-neto-full", "random/train-00000-of-00001.parquet"),
    "cic-neto/test.parquet":
        ("lacg030175/CIC-IoT-2023-neto-full", "random/test-00000-of-00001.parquet"),
}
CIC_FULL = [RAW / "cic-neto/train.parquet", RAW / "cic-neto/test.parquet"]

# Public Kaggle datasets, fetched anonymously through the same URLs the dataset pages give
# for curl. Each URL redirects to a signed storage link.
KAGGLE = "https://www.kaggle.com/api/v1/datasets"
KAGGLE_EDGE = "mohamedamineferrag/edgeiiotset-cyber-security-dataset-of-iot-iiot"
KAGGLE_TII = "daniaherzalla/tii-ssrc-23"
EDGE_BUNDLE = RAW / "edgeiiotset-cyber-security-dataset-of-iot-iiot.zip"
EDGE_FULL = RAW / "edge-full"
EDGE_PREFIX = "Edge-IIoTset dataset/"
EDGE_FOLDERS = ("Attack traffic/", "Normal traffic/")   # the per-attack and per-sensor CSVs
TII_CSV = RAW / "tii" / "data.csv"
DOWNLOAD_HELP = "run: python data.py download"

# A full release is far too large to hold, so each is read once into a cached pool of at
# most this many rows per family (see Pool). A federation takes at most its budget from any
# one family, so a cap at the largest budget run (1M rows) never runs a class dry.
FAMILY_CAP = 1_000_000
POOLS = RAW / "pools"


def download() -> None:
    """Fetch every raw file and verify each against its published size.

    A truncated download parses without complaint and silently loses rows, so the size
    check is what makes a finished download trustworthy. A file gets its real name only
    once verified.
    """
    for target, (repo, path) in HF_FILES.items():
        _fetch(RAW / target, f"https://huggingface.co/datasets/{repo}/resolve/main/{path}",
               _hub_size(repo, path))
    _fetch(TII_CSV, f"{KAGGLE}/download/{KAGGLE_TII}/{urllib.parse.quote('csv/data.csv', safe='')}",
           _kaggle_files(KAGGLE_TII)["csv/data.csv"])
    _download_edge()


def _fetch(dest: Path, url: str, expected: int) -> None:
    if _have(dest, expected):
        return
    partial = dest.with_name(dest.name + ".part")
    _stream(url, partial)
    _accept(partial, dest, expected)


def _stream(url: str, partial: Path) -> None:
    """Download url into partial, failing if fewer bytes arrive than the server announced."""
    partial.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as response, partial.open("wb") as out:
        announced = response.headers.get("Content-Length")
        shutil.copyfileobj(response, out, length=1 << 22)
    if announced is not None and partial.stat().st_size != int(announced):
        raise RuntimeError(f"{partial.name}: got {partial.stat().st_size:,} of {int(announced):,} bytes")


def _have(dest: Path, expected: int) -> bool:
    if dest.exists() and dest.stat().st_size == expected:
        print(f"ok       {dest.relative_to(RAW)} ({expected:,} bytes)")
        return True
    print(f"fetching {dest.relative_to(RAW)} ({expected / 1e6:,.0f} MB)", flush=True)
    return False


def _accept(partial: Path, dest: Path, expected: int) -> None:
    """Unzip if the server zipped the file, check the size, and only then give it its name."""
    if zipfile.is_zipfile(partial):           # Kaggle serves large single files zipped
        unzipped = dest.with_name(dest.name + ".unzip")
        with zipfile.ZipFile(partial) as archive, unzipped.open("wb") as out:
            shutil.copyfileobj(archive.open(archive.namelist()[0]), out, length=1 << 22)
        partial.unlink()
        partial = unzipped
    if partial.stat().st_size != expected:
        raise RuntimeError(f"{dest.name}: got {partial.stat().st_size:,} bytes, expected {expected:,}")
    partial.replace(dest)


def _hub_size(repo: str, path: str) -> int:
    folder = path.rsplit("/", 1)[0] if "/" in path else ""
    url = f"https://huggingface.co/api/datasets/{repo}/tree/main/{folder}"
    with urllib.request.urlopen(url, timeout=60) as response:
        listing = json.load(response)
    return next(item["size"] for item in listing if item["path"] == path)


def _kaggle_files(dataset: str) -> dict[str, int]:
    """Every file in a Kaggle dataset with its size. The listing is public and paginated."""
    files, token = {}, None
    while True:
        query = "?" + urllib.parse.urlencode({"pageToken": token}) if token else ""
        with urllib.request.urlopen(f"{KAGGLE}/list/{dataset}{query}", timeout=60) as response:
            page = json.load(response)
        for item in page.get("datasetFiles") or []:
            files[item.get("nameNullable") or item["name"]] = int(
                item.get("totalBytesNullable") or item.get("totalBytes") or 0)
        token = page.get("nextPageToken") or page.get("nextPageTokenNullable")
        if not token:
            return files


def _download_edge() -> None:
    """The 24 per-attack and per-sensor CSVs of Edge-IIoTset.

    Fetched as the dataset's one zip (1.7 GB) rather than file by file (7.7 GB), then only
    those CSVs are unpacked. Reading a zip member checks its CRC, and each unpacked file is
    checked against the size Kaggle lists for it; the set is marked complete only after
    every one has passed, because the loader reads whatever CSVs are present.
    """
    marker = EDGE_FULL / "COMPLETE"
    if marker.exists():
        print(f"ok       edge-full ({marker.read_text(encoding='utf-8').strip()})")
        return
    listed = {name.removeprefix(EDGE_PREFIX): size for name, size in _kaggle_files(KAGGLE_EDGE).items()}
    wanted = {name: size for name, size in listed.items()
              if name.endswith(".csv") and name.startswith(EDGE_FOLDERS)}
    if not EDGE_BUNDLE.exists():
        print(f"fetching {EDGE_BUNDLE.name}", flush=True)
        partial = EDGE_BUNDLE.with_name(EDGE_BUNDLE.name + ".part")
        _stream(f"{KAGGLE}/download/{KAGGLE_EDGE}", partial)
        partial.replace(EDGE_BUNDLE)
    with zipfile.ZipFile(EDGE_BUNDLE) as archive:
        members = {info.filename.removeprefix(EDGE_PREFIX): info.filename for info in archive.infolist()}
        missing = sorted(set(wanted) - set(members))
        if missing:
            raise RuntimeError(f"{EDGE_BUNDLE.name} lacks {missing}")
        for name, size in sorted(wanted.items()):
            dest = EDGE_FULL / name
            if dest.exists() and dest.stat().st_size == size:
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            partial = dest.with_name(dest.name + ".part")
            with archive.open(members[name]) as src, partial.open("wb") as out:
                shutil.copyfileobj(src, out, length=1 << 22)
            if partial.stat().st_size != size:
                raise RuntimeError(f"{name}: unpacked {partial.stat().st_size:,} bytes, Kaggle lists {size:,}")
            partial.replace(dest)
            print(f"unpacked edge-full/{name} ({size / 1e6:,.0f} MB)", flush=True)
    marker.write_text(f"{len(wanted)} files, {sum(wanted.values()):,} bytes\n", encoding="utf-8")


def available() -> list[str]:
    files = {"edge": [EDGE_FULL / "COMPLETE"], "cic": CIC_FULL, "tii": [TII_CSV]}
    return [name for name, paths in files.items() if all(p.exists() for p in paths)]


# ---------- loading: one pool per dataset ----------

@dataclass
class Pool:
    """The rows a dataset's federations are drawn from, with both feature views and both
    label views, and how many rows of each family the whole release holds.

    A small release is held whole. A full one is too large, so its pool keeps up to
    FAMILY_CAP rows of each family, uniform within the family: rare families come whole,
    large ones are cut. The pool's own class mix is therefore not the release's: shares
    come from `release`, and the pool only bounds how many rows can be drawn.
    """
    native: np.ndarray        # the dataset's own numeric features
    native_names: list[str]
    harmonized: np.ndarray    # HARMONIZED columns
    family: np.ndarray        # in-domain class (Fig. 3 family names)
    common: np.ndarray        # 4-class label, "" where the family has no common counterpart
    release: dict[str, int]   # rows of each family in the whole release

    @property
    def source_rows(self) -> int:
        return sum(self.release.values())

    def release_share(self, labels: np.ndarray) -> dict[str, float]:
        """Each label's share of the whole release, for any labelling of the pool's rows.

        Within a family the pool is a uniform sample, so a label's frequency inside the
        family carries over to the release; the family's own weight comes from `release`.
        """
        total = self.source_rows
        share: dict[str, float] = {}
        for fam, rows in self.release.items():
            in_family = self.family == fam
            values, counts = np.unique(labels[in_family], return_counts=True)
            for value, count in zip(values, counts):
                share[value] = share.get(value, 0.0) + rows / total * count / in_family.sum()
        return share


def _counts(labels: np.ndarray) -> dict[str, int]:
    values, counts = np.unique(labels, return_counts=True)
    return {str(v): int(c) for v, c in zip(values, counts)}


EDGE_FAMILY = {
    "Normal": BENIGN,
    "DDoS_UDP": "DoS/DDoS", "DDoS_ICMP": "DoS/DDoS", "DDoS_HTTP": "DoS/DDoS", "DDoS_TCP": "DoS/DDoS",
    "Port_Scanning": "InfoGather", "Vulnerability_scanner": "InfoGather",
    "Fingerprinting": "InfoGather", "OS_Fingerprinting": "InfoGather",
    "SQL_injection": "Injection", "XSS": "Injection", "Uploading": "Injection",
    "MITM": "MITM",
    # Ferrag et al. group password cracking under malware; the paper's common map then
    # calls Edge's "password" attacks brute force (Section 3.3)
    "Backdoor": "Malware", "Ransomware": "Malware", "Password": "Malware",
}
EDGE_COMMON = {"Normal": BENIGN, "DDoS_UDP": "DoS", "DDoS_ICMP": "DoS", "DDoS_HTTP": "DoS",
               "DDoS_TCP": "DoS", "Port_Scanning": "Recon", "Vulnerability_scanner": "Recon",
               "Fingerprinting": "Recon", "OS_Fingerprinting": "Recon", "Password": "BruteForce"}
EDGE_PORTS = ("tcp.dstport", "udp.port", "http.tls_port")   # tcp.srcport is text, dropped anyway
# The numeric fields of the raw release. Wireshark wrote flags and checksums as hex
# ("0x00000018"); the ML release Ferrag et al. derived had already decoded them. Text
# fields (hosts, URIs, payloads, MQTT topics, dns.qry.name) are not features.
EDGE_NUMERIC = (
    "arp.opcode", "arp.hw.size", "icmp.checksum", "icmp.seq_le", "icmp.transmit_timestamp",
    "icmp.unused", "http.content_length", "http.response", "tcp.ack", "tcp.ack_raw",
    "tcp.checksum", "tcp.connection.fin", "tcp.connection.rst", "tcp.connection.syn",
    "tcp.connection.synack", "tcp.flags", "tcp.flags.ack", "tcp.len", "tcp.seq",
    "udp.stream", "udp.time_delta", "dns.qry.name.len", "dns.qry.qu", "dns.qry.type",
    "dns.retransmission", "dns.retransmit_request", "dns.retransmit_request_in",
    "mqtt.conflag.cleansess", "mqtt.conflags", "mqtt.hdrflags", "mqtt.len",
    "mqtt.msg_decoded_as", "mqtt.msgtype", "mqtt.proto_len", "mqtt.topic_len", "mqtt.ver",
    "mbtcp.len", "mbtcp.trans_id", "mbtcp.unit_id",
)

CIC_FAMILY = {"Benign": BENIGN, "DDoS": "DDoS", "DoS": "DoS", "Mirai": "Mirai",
              "Spoofing": "Spoofing", "Recon": "Recon", "Web-based": "Web", "BruteForce": "BruteForce"}
CIC_COMMON = {"Benign": BENIGN, "DDoS": "DoS", "DoS": "DoS", "Recon": "Recon", "BruteForce": "BruteForce"}
CIC_LABELS = ("Label", "Label_orig", "attack_class", "label")

TII_FAMILY = {"DoS": "DoS", "Information Gathering": "InfoGather", "Mirai": "Mirai",
              "Bruteforce": "BruteForce"}
TII_COMMON = {BENIGN: BENIGN, "DoS": "DoS", "InfoGather": "Recon", "BruteForce": "BruteForce"}
TII_LABELS = ("Label", "Traffic Type", "Traffic Subtype")


def load(name: str) -> Pool:
    loaders = {"edge": _load_edge_full, "cic": _load_cic_full, "tii": _load_tii}
    return loaders[name]()


def _family_sample(chunks: Iterable[pd.DataFrame], cap: int, seed: int) -> tuple[pd.DataFrame, dict[str, int]]:
    """Up to `cap` rows of every family from a stream too large to hold, uniform within each
    family, and how many rows of each family the stream had. Chunks carry the family in a
    `_family` column.

    Bottom-k on an i.i.d. random key per row: within a family the `cap` smallest keys are a
    uniform sample without replacement, so the subclasses inside a family keep their
    proportions. Once a family is full, a row only enters by beating its largest kept key,
    so most rows are dropped on arrival. The keys come from one generator in row order, so
    the chunking does not change the sample.
    """
    rng = np.random.default_rng(seed)
    kept: dict[str, pd.DataFrame] = {}
    seen: dict[str, int] = {}
    for chunk in chunks:
        chunk = chunk.assign(_key=rng.random(len(chunk)))
        for fam, part in chunk.groupby("_family", sort=True):
            seen[fam] = seen.get(fam, 0) + len(part)
            have = kept.get(fam)
            if have is not None and len(have) >= cap:
                part = part[part["_key"] < have["_key"].max()]
            both = part if have is None else pd.concat([have, part], ignore_index=True)
            kept[fam] = both.nsmallest(cap, "_key") if len(both) > cap else both
        print(f"  read {sum(seen.values()):,} rows, kept {sum(map(len, kept.values())):,}",
              end="\r", flush=True)
    print()
    sample = pd.concat([kept[f] for f in sorted(kept)], ignore_index=True).drop(columns="_key")
    return sample, dict(sorted(seen.items()))


def _cached_pool(name: str, read: Callable[[], Iterable[pd.DataFrame]], seed: int,
                 prepare: Callable[[pd.DataFrame], pd.DataFrame] = lambda df: df) -> tuple[pd.DataFrame, dict[str, int]]:
    """A full release's pool and family counts, sampled on first use and cached under
    data/raw/pools.

    `prepare` turns the sampled raw rows into the numeric table the loader needs; doing it
    after sampling means only the kept rows are converted.
    """
    cache = POOLS / f"{name}-{FAMILY_CAP}-per-family.parquet"
    meta = cache.with_suffix(".json")
    if not cache.exists():
        print(f"sampling up to {FAMILY_CAP:,} rows per family of {name} (once; cached as {cache.name})",
              flush=True)
        sample, release = _family_sample(read(), FAMILY_CAP, seed)
        POOLS.mkdir(parents=True, exist_ok=True)
        partial = cache.with_name(cache.name + ".part")
        prepare(sample).to_parquet(partial)
        partial.replace(cache)
        meta.write_text(json.dumps({"release": release, "family_cap": FAMILY_CAP, "seed": seed}, indent=1),
                        encoding="utf-8")
    return pd.read_parquet(cache), json.loads(meta.read_text(encoding="utf-8"))["release"]


def _load_edge_full() -> Pool:
    files = sorted(p for folder in EDGE_FOLDERS for p in (EDGE_FULL / folder).rglob("*.csv"))
    columns = list(dict.fromkeys(EDGE_NUMERIC + EDGE_PORTS + ("Attack_type",)))

    def read() -> Iterable[pd.DataFrame]:
        for path in files:
            # as text: hex fields and stray strings would otherwise change a column's
            # type from one chunk to the next
            for chunk in pd.read_csv(path, usecols=columns, dtype=str, keep_default_na=False,
                                     chunksize=1_000_000):
                family = chunk["Attack_type"].map(EDGE_FAMILY)
                if family.isna().any():
                    raise ValueError(f"Edge attack types with no family: "
                                     f"{sorted(set(chunk['Attack_type'][family.isna()]))}")
                yield chunk.assign(_family=family)

    def prepare(df: pd.DataFrame) -> pd.DataFrame:
        return df[["Attack_type"]].assign(**{c: _edge_number(df[c]) for c in columns if c != "Attack_type"})

    df, release = _cached_pool("edge", read, EDGE.seed, prepare)
    return _edge_pool(df, list(EDGE_NUMERIC), release)


def _edge_number(text: pd.Series) -> np.ndarray:
    """Wireshark's text for one field as float32: hex decoded, anything non-numeric 0."""
    value = pd.to_numeric(text, errors="coerce").to_numpy(np.float64, copy=True)
    hexadecimal = text.str.startswith("0x").to_numpy(bool)
    value[hexadecimal] = [int(h, 16) for h in text[hexadecimal]]
    return np.nan_to_num(value).astype(np.float32)


def _edge_pool(df: pd.DataFrame, names: list[str], release: dict[str, int] | None = None) -> Pool:
    flags = df["tcp.flags"].fillna(0).astype(int).to_numpy()
    nonzero = lambda *cols: np.any([df[c].to_numpy() != 0 for c in cols], axis=0)
    harmonized = np.column_stack(
        [(flags & bit) > 0 for bit in TCP_FLAG_BITS.values()]
        + [nonzero("tcp.dstport", "tcp.flags"),
           nonzero("udp.port", "udp.stream", "udp.time_delta"),
           nonzero("icmp.checksum", "icmp.seq_le", "icmp.unused")]
    ).astype(np.float32)
    kind = df["Attack_type"]
    family = kind.map(EDGE_FAMILY).to_numpy(str)
    return Pool(df[names].to_numpy(np.float32), names, harmonized, family,
                kind.map(EDGE_COMMON).fillna("").to_numpy(str), release or _counts(family))


def _load_cic_full() -> Pool:
    if not all(p.exists() for p in CIC_FULL):
        raise FileNotFoundError(f"{CIC_FULL[0].parent} is incomplete; {DOWNLOAD_HELP}")
    columns = [c for c in pq.read_schema(CIC_FULL[0]).names if c not in CIC_LABELS] + ["attack_class"]

    def read() -> Iterable[pd.DataFrame]:
        for path in CIC_FULL:
            for batch in pq.ParquetFile(path).iter_batches(batch_size=1_000_000, columns=columns):
                chunk = batch.to_pandas()
                family = chunk["attack_class"].map(CIC_FAMILY)
                if family.isna().any():
                    raise ValueError(f"CIC attack classes with no family: "
                                     f"{sorted(set(chunk['attack_class'][family.isna()]))}")
                yield chunk.assign(_family=family)

    # named apart from the pool of UNB's later 39-feature release, which this replaced
    df, release = _cached_pool("cic-neto", read, CIC.seed, lambda df: df.drop(columns="_family"))
    return _cic_pool(df, release)


def _cic_pool(df: pd.DataFrame, release: dict[str, int] | None = None) -> Pool:
    names = [c for c in df.columns if c not in CIC_LABELS]
    flag_cols = [f"{flag}_flag_number" for flag in TCP_FLAG_BITS]
    harmonized = _finite(df[flag_cols + ["TCP", "UDP", "ICMP"]].to_numpy(np.float32))
    kind = df["attack_class"]
    unknown = sorted(set(kind) - set(CIC_FAMILY))
    if unknown:
        raise ValueError(f"CIC attack classes with no family: {unknown}")
    family = kind.map(CIC_FAMILY).to_numpy(str)
    return Pool(_finite(df[names].to_numpy(np.float32)), names, harmonized, family,
                kind.map(CIC_COMMON).fillna("").to_numpy(str), release or _counts(family))


def _load_tii() -> Pool:
    """TII-SSRC-23 is 5 GB of CICFlowMeter flows, read once into a cached pool."""
    if not TII_CSV.exists():
        raise FileNotFoundError(f"{TII_CSV} is missing; {DOWNLOAD_HELP}")

    def read() -> Iterable[pd.DataFrame]:
        for chunk in pd.read_csv(TII_CSV, chunksize=1_000_000, low_memory=False):
            missing = [c for c in TII_LABELS if c not in chunk.columns]
            if missing:
                raise ValueError(f"{TII_CSV} has no {missing}; columns are {list(chunk.columns)}")
            benign = chunk["Label"].str.lower() == "benign"
            family = chunk["Traffic Type"].map(TII_FAMILY).where(~benign, BENIGN)
            unknown = sorted(set(chunk["Traffic Type"][family.isna()]))
            if unknown:                       # checked on every row, not only the sampled ones
                raise ValueError(f"TII traffic types with no family: {unknown}")
            # the numeric flow features only, as float32: no ports (Section 4.3) and no text
            # identifiers (flow id, addresses, timestamp)
            numeric = chunk.select_dtypes("number").drop(columns=["Src Port", "Dst Port"])
            yield numeric.astype(np.float32).assign(_family=family)

    df, release = _cached_pool("tii", read, TII.seed)
    names = [c for c in df.columns if c != "_family"]
    packets = (df["Total Fwd Packet"] + df["Total Bwd packets"]).clip(lower=1).to_numpy()
    flag_counts = [f"{flag.upper()} Flag Count" for flag in TCP_FLAG_BITS]
    protocol = df["Protocol"].to_numpy()
    harmonized = np.column_stack(
        [df[c].to_numpy() / packets for c in flag_counts]
        + [protocol == 6, protocol == 17, protocol == 1]
    ).astype(np.float32)
    family = df["_family"].to_numpy(str)
    common = np.array([TII_COMMON.get(f, "") for f in family])
    return Pool(_finite(df[names].to_numpy(np.float32)), names, _finite(harmonized), family, common, release)


def _finite(x: np.ndarray) -> np.ndarray:
    """CICFlowMeter writes inf for rates over zero-length flows; z-scoring cannot use it."""
    return np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)


# ---------- partitioning: the Fig. 3 recipe at a given row budget ----------

def allocate(flows: list[float], benign_share: list[float], families: list[tuple[str, ...]],
             share: dict[str, float], capacity: dict[str, int], rows: int) -> tuple[list[dict[str, int]], int]:
    """How many rows of each class every client gets.

    Client totals follow the Fig. 3 flow ratio, each client's benign share is benign_share,
    and its attack rows are split across the families it holds in proportion to each
    family's `share` of the release. `capacity` is how many rows of each class the pool can
    supply: the budget shrinks if any class would run out, so the proportions hold exactly
    instead of the rarest class being silently topped up.
    """
    weights = np.asarray(flows) / sum(flows)
    per_row: list[dict[str, float]] = []
    for w, b, fams in zip(weights, benign_share, families):
        attacks = sum(share[f] for f in fams)
        client = {BENIGN: w * b}
        client.update({f: w * (1 - b) * share[f] / attacks for f in fams})
        per_row.append(client)

    demand: dict[str, float] = {}
    for client in per_row:
        for f, v in client.items():
            demand[f] = demand.get(f, 0.0) + v
    feasible = min(capacity[f] / d for f, d in demand.items() if d > 0)
    used = int(min(rows, feasible))
    # a class needs a few rows on a client to be split into train/val/test at all; under a
    # full release's real proportions the rarest ones can round to 1 or 2, and such a class
    # is left out of that client instead of failing the stratified split
    return [{f: n for f, v in client.items() if (n := int(v * used)) >= MIN_CLASS_ROWS}
            for client in per_row], used


def deal(labels: np.ndarray, counts: list[dict[str, int]], rng: np.random.Generator) -> list[np.ndarray]:
    """Hand out row indices: each class is shuffled once and dealt to clients in order.

    Classes are shuffled in first-seen order, never set order: string hashing is salted
    per process, and the shuffles share one generator, so set order would deal a
    different partition on every run.
    """
    shuffled = {f: rng.permutation(np.flatnonzero(labels == f))
                for f in dict.fromkeys(f for c in counts for f in c)}
    taken = {f: 0 for f in shuffled}
    clients = []
    for need in counts:
        rows = []
        for f, n in need.items():
            rows.append(shuffled[f][taken[f]:taken[f] + n])
            taken[f] += n
        clients.append(np.concatenate(rows))
    return clients


# ---------- the federation a run trains on ----------

@dataclass
class Client:
    X_train: np.ndarray
    y_train: np.ndarray
    X_val: np.ndarray
    y_val: np.ndarray
    X_test: np.ndarray
    y_test: np.ndarray
    raw_test: np.ndarray       # unscaled, for cross-dataset tests with a foreign scaler
    mean: np.ndarray
    scale: np.ndarray
    key: str

    @property
    def n_train(self) -> int:
        return len(self.y_train)


@dataclass
class Federation:
    scenario: str
    classes: tuple[str, ...]
    features: list[str]
    clients: list[Client]
    rows: int                              # rows actually drawn, before splitting
    sources: list[str] = field(default_factory=list)
    source_rows: dict[str, int] = field(default_factory=dict)   # size of each release used

    @property
    def n_features(self) -> int:
        return len(self.features)

    def stacked(self, split: str) -> tuple[np.ndarray, np.ndarray]:
        """The global evaluation set: every client's split, each scaled by its own scaler."""
        X = np.concatenate([getattr(c, f"X_{split}") for c in self.clients])
        y = np.concatenate([getattr(c, f"y_{split}") for c in self.clients])
        return X, y

    def pooled_scaler(self) -> tuple[np.ndarray, np.ndarray]:
        """One scaler for the whole federation, combined from the clients' statistics.

        Section 5.3 applies "the source-fitted scaler" to a foreign dataset. Each client
        has its own, so the source scaler is their sample-weighted combination — computable
        from (n, mean, variance) alone, without any client revealing a row.
        """
        n = np.array([c.n_train for c in self.clients], dtype=float)
        means = np.stack([c.mean for c in self.clients])
        variances = np.stack([c.scale for c in self.clients]) ** 2
        mean = (n[:, None] * means).sum(0) / n.sum()
        var = (n[:, None] * (variances + (means - mean) ** 2)).sum(0) / n.sum()
        return mean, _safe_scale(np.sqrt(var))


SCENARIOS = ("edge", "cic", "tii", "edge-h", "cic-h", "tii-h", "combined")


def dataset_of(scenario: str) -> str:
    """Which Fabric channel family a scenario belongs to: the harmonized view of a dataset
    has the same clients as the dataset itself, so it shares that dataset's swarm."""
    return scenario.removesuffix("-h")


def benign_share(spec: DatasetSpec, pool: Pool) -> float:
    """Fig. 3's benign share for this dataset's clients, or the release's own share."""
    return spec.benign_share if spec.benign_share is not None else pool.release.get(BENIGN, 0) / pool.source_rows


def build(scenario: str, rows: int, pools: dict[str, Pool] | None = None) -> Federation:
    """The clients of one scenario, split and scaled.

    edge / cic / tii        in-domain: native features, the dataset's own families
    edge-h / cic-h / tii-h  the same clients through the shared schema and 4 classes,
                            trained to be tested on the other datasets
    combined                one client per dataset (Table 2), shared schema, 4 classes

    `pools` caches loaded datasets between calls.
    """
    pools = pools if pools is not None else {}

    def get(name: str) -> Pool:
        if name not in pools:
            pools[name] = load(name)
        return pools[name]

    if scenario == "combined":
        names = [n for n in ("edge", "cic", "tii") if n in available()]
        if len(names) < 2:
            raise FileNotFoundError("the combined scenario needs at least two datasets")
        specs = [DATASETS[n] for n in names]
        sources = [get(n) for n in names]
        common_fams = tuple(c for c in COMMON_CLASSES if c != BENIGN)
        # each dataset contributes only the common classes it actually has
        fams = [tuple(f for f in common_fams if (p.common == f).any()) for p in sources]
        # per-client availability is that dataset's own rows; allocate one client at a time
        # against a budget split by the Table 1 sizes, then deal from each dataset's pool
        weights = np.array([s.flows_millions for s in specs])
        weights = weights / weights.sum()
        rng = np.random.default_rng(GLOBAL_SEED)
        clients, drawn = [], 0
        for spec, pool, f, w in zip(specs, sources, fams, weights):
            share = pool.release_share(pool.common)
            capacity = _counts(pool.common)
            counts, used = allocate([1.0], [benign_share(spec, pool)], [f], share, capacity, int(rows * w))
            idx = deal(pool.common, counts, rng)[0]
            clients.append(_split(pool.harmonized[idx], pool.common[idx], COMMON_CLASSES,
                                  spec.seed, spec.name))
            drawn += used
        return Federation(scenario, COMMON_CLASSES, list(HARMONIZED), clients, drawn, names,
                          {n: p.source_rows for n, p in zip(names, sources)})

    name = dataset_of(scenario)
    spec, pool = DATASETS[name], get(name)
    counts, used = allocate([c.flows for c in spec.clients], [benign_share(spec, pool)] * len(spec.clients),
                            [c.families for c in spec.clients], pool.release_share(pool.family),
                            _counts(pool.family), rows)
    parts = deal(pool.family, counts, np.random.default_rng(spec.seed))

    clients = []
    for part, cspec in zip(parts, spec.clients):
        if scenario.endswith("-h"):
            part = part[pool.common[part] != ""]
            clients.append(_split(pool.harmonized[part], pool.common[part], COMMON_CLASSES,
                                  spec.seed, cspec.key))
        else:
            clients.append(_split(pool.native[part], pool.family[part], spec.families,
                                  spec.seed, cspec.key))
    released = {name: pool.source_rows}
    if scenario.endswith("-h"):
        return Federation(scenario, COMMON_CLASSES, list(HARMONIZED), clients, used, [name], released)
    return Federation(scenario, spec.families, pool.native_names, clients, used, [name], released)


def _split(X: np.ndarray, labels: np.ndarray, classes: tuple[str, ...], seed: int, key: str) -> Client:
    y = _encode(labels, classes)
    X_rest, X_test, y_rest, y_test = train_test_split(
        X, y, test_size=TEST_SHARE, stratify=y, random_state=seed)
    X_train, X_val, y_train, y_val = train_test_split(
        X_rest, y_rest, test_size=VAL_SHARE, stratify=y_rest, random_state=seed)
    mean = X_train.mean(axis=0)
    scale = _safe_scale(X_train.std(axis=0))
    z = lambda a: ((a - mean) / scale).astype(np.float32)
    return Client(z(X_train), y_train, z(X_val), y_val, z(X_test), y_test, X_test, mean, scale, key)


def _encode(labels: np.ndarray, classes: tuple[str, ...]) -> np.ndarray:
    index = {c: i for i, c in enumerate(classes)}
    return np.array([index[label] for label in labels], dtype=np.int64)


def _safe_scale(std: np.ndarray) -> np.ndarray:
    """A constant column has no spread to divide by; sklearn's StandardScaler uses 1 too."""
    return np.where(std > 0, std, 1.0).astype(np.float32)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch the datasets and check every file's size.")
    parser.add_argument("command", choices=["download"])
    parser.parse_args()
    download()
