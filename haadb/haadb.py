# -*- coding: utf-8 -*-
"""
    haadb.HaaDB
    ~~~~~~~~~

    Hive-as-a-DB SDK for Python.

    :copyright: 2022 Rodney Maniego Jr.
    :license: MIT License
"""


import ast
import json
import time
import binascii
from nektar import Nektar
from cryptography.fernet import Fernet


HAADB_VERSION = "1.0.0"


class HaaDB:
    """HaaDB base class.
    ~~~~~~~~~

    :param username: a valid Hive account username
    :param wifs: a dictionary of roles and their equivalent WIFs
    :param nodes: a list of valid Hive Blockchain nodes (Default value = None)
    :param chain_id: the blockchain id (Default value = None)
    :param limit: size of each chunked data (Default value = 4096)
    :param timeout: seconds before the request is dropped (Default value = 10)
    :param retries: times the request retries if errors are encountered (Default value = 3)
    :param warning: display warning messages (Default value = False)

    """

    def __init__(
        self,
        username,
        wifs,
        nodes=None,
        chain_id=None,
        limit=4096,
        timeout=10,
        retries=3,
        warning=False,
    ):
        self.hive = Nektar(
            username=username,
            wifs=wifs,
            nodes=nodes,
            chain_id=chain_id,
            timeout=10,
            retries=3,
            warning=warning,
        )

        self._username = username
        if not (1024 <= int(limit) <= 4096):
            raise HaaDBException("`limit` must be between 1024 and 4096 only.")

        # adjusted limit, with overhead
        self._limit = limit - 512

    def get_marker(self):
        """Get the last known transaction id prior to last transaction, used to speed up the account history traversal."""
        params = [self._username, -1, 10]
        results = self.hive.appbase.condenser().get_account_history(params)
        return max(((results[0][0] // 1000) * 1000) - 1000, 1000)

    def generate_encryption_key(self):
        """Generate a Fernet encryption key."""
        return _new_encryption_key()

    def broadcast(self, cid, data, encryption_key=None, posting=True):
        """Format data and broadcast as custom JSON.

        :param cid: contract id, any valid string using lowercase alphabet, numbers, and dashes/underscores only
        :param data: a value of any data type: string, int, or other object data
        :param encryption_key: fernet generated string to encrypt data (Default value = None)
        :param posting: use posting keys, otherwhise use active key (Default value = True)
        """

        if not isinstance(cid, str):
            raise HaaDBException("`cid` must be a valid string.")

        if not isinstance(posting, bool):
            raise HaaDBException("`posting` must be `True` or `False` only.")

        dtype = _get_dtype(data)
        processed_data = _get_bytes(data)
        if not isinstance(data, (str, int, float)):
            processed_data = binascii.hexlify(processed_data)

        if isinstance(encryption_key, str):
            cypher = _load_cypher(encryption_key)
            processed_data = cypher.encrypt(processed_data)
        processed_data = processed_data.decode("utf-8")

        required_posting_auths = []
        required_auths = [self._username]
        if posting:
            required_auths = []
            required_posting_auths = [self._username]

        s = 1
        timestamp = int(time.time())
        batches = (len(processed_data) // self._limit) + 1
        for i in range(batches):
            width = (i + 1) * self._limit
            jdata = {}
            jdata["haadb"] = HAADB_VERSION
            jdata["timestamp"] = timestamp
            if batches > 1:
                jdata["batch"] = [(i + 1), batches]
            jdata["dtype"] = dtype
            jdata["data"] = processed_data[s - 1 : width - 1]
            self.hive.custom_json(
                cid,
                jdata,
                required_posting_auths=required_posting_auths,
                required_auths=required_auths,
                debug=True,
            )
            s = width

    def fetch(self, cid, encryption_key=None, start=1000, strict=True, latest=True):
        """Rebuild data from custom JSON chunks.

        :param cid: contract id, any valid string using lowercase alphabet, numbers, and dashes/underscores only
        :param encryption_key: fernet generated string to encrypt data (Default value = None)
        :param start: initial starting transaction (Default value = 1000)
        :param strict: discard incomplete contracts (Default value = True)
        :param latest: return the most recent version (Default value = 1000)
        """

        if int(start) < 1000 or (start % 1000 > 0):
            raise HaaDBException("`start` must be a value by the factor of 1000.")

        top = 0
        versions = {}
        params = [self._username, -1, 1000]
        while True:
            try:
                result = self.hive.appbase.condenser().get_account_history(params)
                params[1] += 1000
            except:
                params[1] += 1000
                continue
            tids = [1000]
            for item in result:
                if top == 0:
                    tids.append(item[0])
                if item[1]["op"][0] != "custom_json":
                    continue
                operation = item[1]["op"][1]
                if operation["id"] != cid:
                    continue
                jdata = json.loads(operation["json"])
                if "haadb" not in jdata:
                    continue
                ts = jdata["timestamp"]
                batches = [1, 1]
                if "batches" in jdata:
                    batches = jdata["batches"]
                if ts not in versions:
                    versions[ts] = {
                        "batches": batches[1],
                        "dtype": jdata["dtype"],
                        "data": {},
                    }
                versions[ts]["data"][batches[0]] = jdata["data"]
            if top == 0:
                params[1] = start
                top = max(tids) + 1000
            if params[1] > top:
                break

        constructed = {}
        for ts, chunks in versions.items():
            if strict and (chunks["batches"] != len(chunks["data"])):
                continue
            constructed[ts] = _construct(chunks, encryption_key)

        if latest:
            if constructed:
                ts = max(list(constructed.keys()))
                return constructed[ts]
            return ""
        return constructed


def _construct(chunks, encryption_key):
    """Rebuild data from formatted chunks.

    :param chunks: a formatted dictionary from the fetch method
    :param encryption_key: fernet generated string to encrypt data
    """
    if not chunks["data"]:
        return ""
    dtype = chunks["dtype"]
    parts = sorted(chunks["data"])
    data = "".join([b for a, b in chunks["data"].items()]).encode("utf-8")
    if isinstance(encryption_key, str):
        cypher = _load_cypher(encryption_key)
        try:
            data = cypher.decrypt(data).decode()
        except:
            return str(data, "utf-8")

    if dtype not in ("str", "int", "float"):
        data = binascii.unhexlify(data)
    if isinstance(data, bytes):
        data = str(data, "utf-8")
    if dtype not in ("str", "object"):
        if dtype == "int":
            return int(data)
        if dtype == "float":
            return float(data)
        return ast.literal_eval(data)
    return data


def _get_dtype(obj):
    """Get the native data type.

    :param obj: any Python object
    """
    if hasattr(obj, "__bytes__"):
        return "object"
    return str(type(obj))[8:][:-2]


def _get_bytes(obj, encoding="utf-8"):
    """Get the native data type.

    :param obj: any Python object
    :param encoding: string encoding (Default value = utf-8)
    """
    if hasattr(obj, "__bytes__"):
        return obj.__bytes__()
    return bytes(str(obj), encoding)


def _new_encryption_key():
    """Generate a Fernet encryption key."""
    return Fernet.generate_key().decode()


def _load_cypher(encryption_key):
    """Generate a Fernet cypher from the encryption key."""
    return Fernet(encryption_key.encode("utf-8"))


class HaaDBException(Exception):
    """Custom HaaDB Exception.

    :param message: a valid string
    """

    def __init__(self, message):
        super().__init__(message)
