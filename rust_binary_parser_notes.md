tags:

* rust

* parsing

* telemetry

* low-level

* binary
  date_created: 2026-11-07
  status: in-progress

# 🦀 Rust Binary Parser: MoTeC Telemetry Notes

> \[!abstract\] Overview
> Course notes and practical handbook for building a high-performance binary file parser for **MoTeC telemetry (`.ld` and `.ldx`)** files from scratch in **Rust**. Focuses on low-level memory layout, zero-copy parsing, and idiomatic error handling.

## 🧭 Core Mental Models & Analogies

### 1. References (`&`) vs Values

* **By Value (Copy / Move):** Photocopying an entire 1,000-page book to hand it to a friend. Expensive and consumes unnecessary RAM.

* **By Reference (`&`):** Leaving the book on your desk and handing your friend a sticky note that says *"Read page 42"*. Zero overhead.

### 2. Slices (`&[u8]`) as Fat Pointers

A slice does **not** allocate memory or clone bytes. It is a tiny 16-byte structure on 64-bit architectures containing:

1. **Pointer (`*const u8`):** Memory address of the first byte.

2. **Length (`usize`):** Number of consecutive bytes to view.

```
Buffer in RAM:  [ 'M' | 'o' | 'T' | 'e' | 'C' | 0x01 | 0x00 | 0x80 | 0x3F ]
                  ▲                             ▲
                  │                             │
Slice &[u8]:      └── pointer: 0x1000 ──────────┘
                      length: 5

```

## 🔢 Data Types & Primitive Storage

> \[!important\] The Binary Golden Rule
> Memory addresses reference **whole bytes**, not individual bits. Data types in parser structs must **exactly match** the field sizes specified by the binary protocol format.

| Rust Type | Size (Bytes) | Size (Bits) | Range | Common Telemetry Application | 
| ----- | ----- | ----- | ----- | ----- | 
| `u8` | $1$ | $8$ | $0 \dots 255$ | Flags, Pedal inputs ($0 \dots 100\%$), byte markers | 
| `u16` | $2$ | $16$ | $0 \dots 65,535$ | Engine RPM, sensor sample frequencies | 
| `u32` | $4$ | $32$ | $0 \dots \approx 4.29 \times 10^9$ | File offsets, total sample counts | 
| `f32` | $4$ | $32$ | IEEE 754 float | Vehicle speed (km/h), boost pressure, temperatures | 
| `usize` | Target | 32 or 64 | $0 \dots \text{RAM limit}$ | Array lengths, memory offsets, indexing | 

## 🔄 Endianness (Byte Ordering)

Telemetry loggers convert numbers larger than $255$ into discrete bytes for storage.

* **Big-Endian:** Most significant (biggest) byte is stored first.

* **Little-Endian:** Least significant (smallest) byte is stored first (default on x86, ARM, and MoTeC format).

### Reconstruction Formula for Little-Endian:

$$
\text{Value} = \text{Byte}_0 + (\text{Byte}_1 \times 256) + (\text{Byte}_2 \times 256^2) + \dots
$$

```
// Standard library zero-cost conversions:
let rpm_bytes: [u8; 2] = [0x01, 0x02];
let rpm: u16 = u16::from_le_bytes(rpm_bytes); // 1 + (2 * 256) = 513

```

## 🛠️ File I/O & Cursor Navigation

```
use std::fs::File;
use std::io::{Read, Seek, SeekFrom};

// Opening a file with error propagation
let mut file = File::open("sample.ld")?;

// 1. Reading an exact number of bytes into a fixed buffer
let mut buffer = [0u8; 4];
file.read_exact(&mut buffer)?; // Cursor advances automatically by 4 bytes

// 2. Seeking (jumping) to a specific offset without reading intermediate bytes
file.seek(SeekFrom::Start(1024))?; // Jumps directly to byte 1024 from file start

```

### Reading Behavior Matrix

* `[0u8; N]` allocates an array of $N$ zeros on the stack.

* `file.read_exact(&mut buf)?` modifies the array in-place and advances the internal read head by $N$.

* The `?` operator unwrap values inside `Ok(...)` or immediately returns `Err(...)` to the caller.

## 🧱 Structs vs OOP Classes

Rust splits the traditional OOP `class` into data definitions and behavior blocks:

```
// Data layout (like fields in a class)
struct TelemetryChannel {
    id: u16,
    rate_hz: u16,
    data_offset: u32,
}

// Behavioral methods (like methods in a class)
impl TelemetryChannel {
    // &self borrows the struct without taking ownership or copying
    fn print_summary(&self) {
        println!("Channel ID: {}, Rate: {} Hz", self.id, self.rate_hz);
    }
}

```

## 🎯 Capstone Challenge: MoTeC `.ld` Header Parser

### Specification

* **Bytes** $0 \dots 3$: Magic signature (`u32`, Little-Endian, expected `0x40`).

* **Bytes** $4 \dots 5$: Format version (`u16`, Little-Endian).

* **Bytes** $8 \dots 11$: Channel metadata pointer (`u32`, Little-Endian).

### Implementation Checklist

* \[ \] Define `struct Header` with `magic`, `version`, and `channel_meta_ptr`.

* \[ \] Implement `fn parse_header(file: &mut File) -> Result<Header, std::io::Error>`.

* \[ \] Ensure byte buffers use correct lengths (`[0u8; 4]`, `[0u8; 2]`).

* \[ \] Convert byte sequences using `from_le_bytes`.

* \[ \] Construct and return `Ok(Header { ... })`.