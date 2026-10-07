# Guarded GPU framework on the aligned Gravity kernel

This trial uses the maintained 7.1.13 baseline and its USB/WFI patches. It adds
Rust and the Gravity M4 driver, with T6040 normal startup explicitly refused and
probe-only enabled by default. T6040 identification returns before any donor
T8132 power/MCC/object builder. Mapping for identification ends at 0xd04020;
the complete T6040 register aperture is 0x3758000, smaller than the donor 64 MiB.

Prepare a new workspace (do not overwrite a booted build):

```sh
python3 experiments/t6040-gpu/gravity-contract/prepare.py \
  out/gravity-kernel-alignment/linux out/new-gpu-work/linux
python3 experiments/t6040-gpu/gravity-contract/build.py out/new-gpu-work --jobs 8
python3 experiments/t6040-gpu/gravity-contract/package.py out/new-gpu-work
```

No GPU node is automatically added and no rendering is enabled. The kernel
trial first qualifies the framework and maintained peripherals; native dynamic
resource qualification follows. Firmware startup remains gated.

The independent `../g16s_abi.rs` codecs model only documented candidate wire
fields. They are not linked into the hardware driver. Test with:

```sh
rustc --edition=2021 --test experiments/t6040-gpu/g16s_abi.rs -o /tmp/g16s-abi-tests
/tmp/g16s-abi-tests
```

Missing contracts include root/main fields not described by the standalone
note, full queue-pointer allocation extent, initialization barriers, allocation
and address-space teardown, and board-specific power/MCC sequencing. Passing
byte-level tests does not validate these layouts against running firmware.

Verified teardown is a priority for avoiding repeated reboot cycles. The donor
completed `Bootstrap` object's destructor calls RTKit shutdown and retains
address spaces if shutdown fails. The underlying Rust RTKit destructor only
frees the RTKit object; it does not itself shut down the coprocessor. Audit
constructor failures after ASC start as well as normal destruction before
enabling T6040 startup. The C shutdown path uses AP QUIESCED followed by IOP
SLEEP and reinitialization; it explicitly warns that using OFF can prevent a
subsequent wake. None of this is a native T6040 teardown qualification yet.
