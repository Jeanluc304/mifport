"""FrameImage: the bitmap format of graphics stored inside a MIF file, turned into PNG.

The format is described in the MIF Reference, chapter "FrameImage Facet Format". It is
close to the Sun rasterfile format: a header of eight 32-bit numbers, an optional colour
map, then the pixels, whose rows are padded to 16 bits and may be run-length encoded.
"""
import struct
import zlib

MAGIC = 0x59a66a95
STANDARD, ENCODED = 1, 2
MAX_PIXELS = 100_000_000   # a header can promise any size: stop before using up the memory


def unpack_runs(data, size):
    """Undo the run-length encoding: 80 nn pp is nn+1 times pp, and 80 00 is one 80."""
    out = bytearray()
    i = 0
    while len(out) < size:
        j = data.find(0x80, i)
        if j < 0:
            out += data[i:]
            break
        out += data[i:j]
        if j + 1 >= len(data):
            raise ValueError('the compressed data ends early')
        if data[j + 1] == 0:
            out.append(0x80)
            i = j + 2
        elif j + 2 >= len(data):
            raise ValueError('the compressed data ends early')
        else:
            out += data[j + 2:j + 3] * (data[j + 1] + 1)
            i = j + 3
    return out


def chunk(kind, data):
    return (struct.pack('>I', len(data)) + kind + data
            + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff))


def to_png(data):
    """PNG data of a FrameImage. Raises ValueError for data that cannot be converted."""
    if len(data) < 32:
        raise ValueError('the header is incomplete')
    magic, width, height, depth, _, kind, _, map_size = struct.unpack('>8I', data[:32])
    if magic != MAGIC:
        raise ValueError('it does not start with the FrameImage number')
    if depth not in (1, 8):
        raise ValueError(f'{depth} bits per pixel are not supported')
    if kind not in (STANDARD, ENCODED):
        raise ValueError(f'unknown data type {kind}')
    if not width or not height or width * height > MAX_PIXELS:
        raise ValueError(f'unusable size {width} x {height}')
    colors = data[32:32 + map_size]
    if len(colors) < map_size:
        raise ValueError('the colour map is incomplete')
    pixels = data[32 + map_size:]
    row = (width * depth + 7) // 8
    stride = row + row % 2     # rows are padded to 16 bits
    size = stride * height
    if kind == ENCODED:
        pixels = unpack_runs(pixels, size)
    if len(pixels) < size:
        raise ValueError('the pixel data is incomplete')

    invert = bytes(255 - b for b in range(256)) if depth == 1 else None  # here 1 is black
    lines = bytearray()
    for y in range(height):
        line = bytes(pixels[y * stride:y * stride + row])
        lines += b'\0' + (line.translate(invert) if invert else line)
    palette = b''
    color_type = 0             # grey
    if depth == 8 and map_size >= 3:
        n = min(map_size // 3, 256)   # all red levels, then all green, then all blue
        red, green, blue = (colors[i * (map_size // 3):][:n] for i in range(3))
        palette = bytes(c for rgb in zip(red, green, blue) for c in rgb)
        color_type = 3         # colours from the palette
    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, depth, color_type, 0, 0, 0))
            + (chunk(b'PLTE', palette) if palette else b'')
            + chunk(b'IDAT', zlib.compress(bytes(lines)))
            + chunk(b'IEND', b''))
