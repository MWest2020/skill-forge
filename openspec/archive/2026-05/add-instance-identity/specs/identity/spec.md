# Spec — identity module

Lives at `src/skill_forge/identity.py`. Single file — under 200 lines is enough
to cover keypair management, signing, and canonicalization.

## On-disk layout

```
{home}/identity/
├── private_key.pem    # PEM-encoded Ed25519 private key, mode 0600
├── public_key.pem     # PEM-encoded Ed25519 public key, mode 0644
└── instance_id.txt    # human-readable id, one line, no trailing newline guarantee
```

`{home}` defaults to `~/.config/skill-forge/`. Override via the `home` argument
of every public function (no global state). The directory is created `0700` on
first generation.

## Identity dataclass

```python
@dataclass(frozen=True)
class Identity:
    instance_id: str       # forge-<8-hex>
    public_key: Ed25519PublicKey
    private_key: Ed25519PrivateKey
    home: Path             # the {home}/identity/ root
```

Frozen because identity is immutable within a process. `home` is kept so
callers don't have to thread the path separately when issuing follow-up
operations (e.g., `Identity.backup_path()`).

## Public API

```python
def get_or_create(home: Path) -> Identity: ...
def from_seed(home: Path, seed: bytes) -> Identity: ...   # tests only
def sign_skill(skill: Skill, identity: Identity) -> str: ...
def verify_skill(skill: Skill, identity: Identity) -> bool: ...
def canonical_payload(skill: Skill) -> bytes: ...
```

### `get_or_create(home)`

- If `{home}/identity/private_key.pem` exists with mode `0600`, load it.
- If it exists but the mode is not `0600`, raise `IdentityKeyPermissionError`
  with the actual mode in the message. Do **not** auto-chmod (silent fixups
  hide compromise).
- If it does not exist, generate a new Ed25519 keypair, write both files
  with correct permissions, derive `instance_id`, write `instance_id.txt`,
  and return the new `Identity`.

### `from_seed(home, seed: bytes)`

- Test helper. `seed` is 32 raw bytes used as the Ed25519 private-key seed.
- Writes the same on-disk layout. Same input → same instance ID, byte-for-byte.

### Instance ID format

`forge-<8-hex>` where the 8 hex chars are the first 8 of
`sha256(public_key_raw_bytes).hexdigest()`. Deterministic from the public
key, so reinstalling with the same keypair gives the same instance ID.

## Canonical payload

The bytes that get signed. Stable across processes and Python versions.

```python
def canonical_payload(skill: Skill) -> bytes:
    body_sha256 = hashlib.sha256(skill.body.encode("utf-8")).hexdigest()
    payload = skill.model_dump(mode="json", exclude={"signature", "body"})
    payload["body_sha256"] = body_sha256
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
```

Properties:

- `signature` is excluded (chicken-and-egg).
- `body` is replaced with `body_sha256` so the payload is compact and the
  body is still tamper-evident.
- `sort_keys=True` + `separators=(",", ":")` make the bytes reproducible.
- All other frontmatter fields (including `origin`) are included.

## Signing and verification

```python
def sign_skill(skill, identity) -> str:
    payload = canonical_payload(skill)
    raw_sig = identity.private_key.sign(payload)
    return base64.b64encode(raw_sig).decode("ascii")

def verify_skill(skill, identity) -> bool:
    if skill.signature is None:
        return False                  # callers decide what to do with missing sigs
    payload = canonical_payload(skill)
    try:
        identity.public_key.verify(base64.b64decode(skill.signature), payload)
        return True
    except InvalidSignature:
        return False
```

`storage.read_skill` calls `verify_skill` and raises `SignatureMismatchError`
on `False` — only for skills whose `origin` starts with our `instance_id`.
Foreign-origin skills are loaded without verification (federation lands the
public-key lookup mechanism).

## Errors

- `IdentityKeyPermissionError` — private key file mode is not `0600`.
- `SignatureMismatchError` — verification returned `False` for a skill we
  expected to be able to verify. The error message names the slug and the
  expected vs. seen origin.

Both subclass `IdentityError`, which subclasses `Exception`.

## Out of scope

- Key rotation, hardware-backed keys, encryption at rest of the private
  key, OS-keyring integration. All separate changes.
- Verifying foreign signatures. Federation problem.
