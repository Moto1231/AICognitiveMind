# Owner-encrypted memory pilot

This is an opt-in-by-caller storage adapter for new test records, not a switch
for any existing Mind. It does not read or convert the existing journal,
change identity, or enable Community Memory. Run it only inside an
owner-controlled process, with a fresh isolated Surreal database.

`OwnerEncryptedMemory.create` encrypts the record before sending anything to
Surreal. The stored row contains a random lookup ID and an authenticated
encrypted envelope. The owner keeps the key and record references, including
the account, Mind, record ID and version. `recall` takes a bounded set of those
references, retrieves encrypted rows and matches the phrase locally. Do not
put the owner key in the hosted service's environment or send the search
phrase, references, or unfiltered plaintext to a hosted model.

The adapter never overwrites an existing locator or falls back to plaintext.
An authorized database operator can still see row sizes and access patterns,
delete records, or refuse to serve them. This feature does not prevent those
availability and metadata effects; authentication detects ciphertext or
binding changes. It does not provide key recovery or a durable owner-side
reference catalog.

Before conversion of existing data, establish how a trusted owner-side host
will support ordinary recall, persist the references, and recover keys. Check
the other places production may retain copies, including journal commit
receipts, diagnostics, exports, and backups, before claiming that private
content is no longer readable by the service. Keep the same Mind and identity.
