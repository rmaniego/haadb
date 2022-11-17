# haadb
Hive-as-a-DB SDK for Python.

Leveraging Hive custom JSONs to store both text-based and binary data. Hive Custom JSONs are limited to 4096 KB includng overheads, HaaDB breaks data into chunks whenever required.

When using objects such as images, files, etc., make sure you have processed it into hex-strings, for example, else it might use class names, pointers, or other data that may result to data loss.

## Official Release
**HaaDB** can now be used on your Python projects through PyPi by running pip command on a Python-ready environment.

`pip install haadb -U`

Current version is 1.0.\*, but more updates are coming soon.

This is compatible with Python 3.9 or later.

## WARNINGS:
 - This package is still under development, some future breakage is inevitable.
 - All `write` transactions in the Hive Blockchain incurs RC costs.
 - Do NOT copy your private keys in your codes!

## HaaDB Modules. 

***WARNING:*** Store WIFs securely in a separate file! 

**Import Module**
```python
from haadb import HaaDB
```

**Initialization** 
```python

# Warning: Do NOT store your WIFs in the code,
# or in the repository!
username = "valid-username"
wifs = { "active": "5*" , "posting": "5*"}

# `limit` --> bytes size before the string representation
# before the string is sliced into chunks, 1024-4096 (default 4096)
limit = 1024 

# basic usage
db = HaaDB(username, wifs=wifs, limit=limit)
```

**Optimization** 
> Get the last known transaction id
> and store in your app configuration.
> This will optimize the traversal in the account history.
```python
marker = hive.get_marker()
```

**Encryption** 
> Generate a unique encryption key and store securely,
> to avoid data loss. You can create separate encryption keys
> for different contracts, or depending on your needs.
```python
ek = hive.generate_encryption_key()
```

**Broadcasting unencrypted data using custom JSONs** 
```python
cid = "store-integers-v1"
data = 1234567890
hive.broadcast(cid, data)
```

**Fetching unencrypted data (all versions)** 
```python
cid = "store-integers-v1"
result = hive.fetch(cid, start=marker, latest=False)
for timestamp, content in result.items():
    print(timestamp, content)
```

**Fetching unencrypted data (latest version)** 
```python
cid = "store-integers-v1"
result = hive.fetch(cid, start=marker)
print("\nResult:", result, type(result))
```

**Broadcasting encrypted data using custom JSONs** 
```python
cid = "store_encrypted_string_v1"
data = "Lorem ipsum, this is a secret message..."
hive.broadcast(cid, data, encryption_key=ek)
```

**Fetching encrypted data (all versions)** 
```python
cid = "store_encrypted_string_v1"
result = hive.fetch(cid, encryption_key=ek, start=marker, latest=False)
for timestamp, content in result.items():
    print(timestamp, content)
```

**Fetching encrypted data (latest versions)** 
```python
cid = "store_encrypted_string_v1"
result = hive.fetch(cid, encryption_key=ek, start=marker)
print("\nResult:", result, type(result)
```

**Lists, dictionaries, and other objects.**
> All native data types can be converted back,
> but other objects will be returned
> as string representation instead.
```python
cid = "native_list_v1"
data = [1, "2", 3.4]
hive.broadcast(cid, data, encryption_key=ek)
result = hive.fetch(cid, encryption_key=ek, start=marker)
print("\nResult:", result, type(result)

cid = "native_dict_v1"
data = { "message": "Hello, world!"}
hive.broadcast(cid, data, encryption_key=ek)
result = hive.fetch(cid, encryption_key=ek, start=marker)
print("\nResult:", result, type(result)
```
