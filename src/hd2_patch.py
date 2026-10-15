import struct
MAGIC = 0xF0000011
LUA = 0xa14e8dfa2cd117e2
def resource_hash(name):
    data = name.encode('utf-8'); mask, mix = (1 << 64) - 1, 0xC6A4A7935BD1E995
    value = len(data) * mix & mask; end = len(data) // 8 * 8
    for (word,) in struct.iter_unpack('<Q', data[:end]):
        word = word * mix & mask; word ^= word >> 47
        value = (value ^ (word * mix & mask)) * mix & mask
    if data[end:]:
        value = (value ^ int.from_bytes(data[end:], 'little')) * mix & mask
    value ^= value >> 47; value = value * mix & mask; value ^= value >> 47
    return value
def lua_resource(src_bytes):
    return struct.pack('<II', len(src_bytes), 2) + src_bytes
def write_lua_archive(path, entries, header12_72):
    head = struct.pack('<III', MAGIC, 1, len(entries)) + header12_72
    head += struct.pack('<QQQII', 0, LUA, len(entries), 16, 16)
    cursor = len(head) + 80 * len(entries); rows = body = b''
    for i, (fid, data) in enumerate(entries):
        pad = -cursor % 16; body += b'\0' * pad; cursor += pad
        rows += struct.pack('<7Q6I', fid, LUA, cursor, 0, 0, 0, 0, len(data), 0, 0, 16, 16, i)
        body += data; cursor += len(data)
    out = head + rows + body
    open(path, 'wb').write(out)
    open(path + '.gpu_resources', 'wb').write(b'')
    open(path + '.stream', 'wb').write(b'')
    return out
