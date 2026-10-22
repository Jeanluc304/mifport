# Security policy

> **No network access – tested on every change.** mifport reads your MIF files and writes
> the converted files, nothing else: it never connects to the network, never sends the
> content of your documents anywhere, and never starts other programs. An automated test
> checks this on every pull request and every push to `main`; see
> [No network access, and how to check it](#no-network-access-and-how-to-check-it) for the
> test and for three ways to verify it yourself.

## No network access, and how to check it

**This is tested automatically.** `NoNetworkTest` in `tests/test_mifdoc.py` converts the
test document with every converter and output format (`mif2md` in both flavours,
`mif2adoc`, `mif2rtf`, also with `--list-tags`, `--dump` and `--version`) under a Python
audit hook that ends the process as soon as it tries to open a socket, resolve a host
name, use HTTP, FTP or mail, open a browser or start another program. A second test makes
sure the hook really catches a connection attempt. GitHub Actions runs these tests on
every pull request and every push to `main` (`.github/workflows/check.yml`): a change
that makes a conversion use the network fails the checks. The test can only see the code
that converting the test document runs; the code search in point 1 below covers the rest.

The converters use only Python's standard library modules for text, files and the command
line. They import no network module (`socket`, `urllib`, `http.client`, `ssl`), start no
other programs, and send nothing anywhere – neither the converted text nor anything
else. You do not have to take this on trust:

1. **Read the code.** There are no dependencies; this finds every place that could reach
   the network or start a program. The only hits are two lines in `mifdoc/builder.py`
   that handle a graphic's web address: it is written into the output as a link, not
   downloaded.

   ```
   grep -nE "socket|urllib|http|ssl|requests|subprocess|os\.system|popen|exec\(|eval\(|importlib|ctypes" mif2*.py mifdoc/*.py
   ```

2. **Watch a conversion.** On Linux, `strace` lists every network system call of a
   process and its children; for the converters the list is empty:

   ```
   strace -f -e trace=network python3 mif2rtf.py input.mif output.rtf
   ```

3. **Convert without a network.** `unshare -rn` (Linux, no root needed) runs the
   converter in a network namespace of its own, without any network device. The
   conversion works the same and the output is identical. For confidential documents
   this is the simplest guarantee, because it holds whatever the code does:

   ```
   unshare -rn python3 mif2rtf.py input.mif output.rtf
   ```

   On other systems, a container without network (`docker run --network none ...`) does
   the same.

What happens **after** the conversion is outside the converters: if a MIF file refers to
a graphic by web address, the Markdown or AsciiDoc output contains that address, and a
viewer (GitHub, pandoc with `--embed-resources`, Asciidoctor with `allow-uri-read`) may
load it. Word and LibreOffice Writer open links in the RTF only when you click them.
Check the version you run: use a release tag and look at what changed since the last
one you checked (`git diff v0.2.0..main`).

## Reporting a vulnerability

Please report security problems privately, not in a public issue: use **"Report a
vulnerability"** on the repository's *Security* tab (GitHub's private vulnerability
reporting). Include a MIF file or steps that show the problem if you can.

You can expect a first answer within two weeks. This is a small spare-time project,
so fixes may take longer; the report stays private until a fix is available.

## Supported versions

Only the latest version on `main` receives fixes.

## What to be aware of when converting untrusted files

mif2md, mif2adoc and mif2rtf read MIF files and the files they refer to. Treat a MIF file from an
unknown source like any other untrusted document:

- **Referenced files are read from anywhere.** A MIF file names its imported graphics by
  path, and the converters follow relative paths (including `../`) and absolute paths.
  Graphics that are found are **copied** into the `images/` folder next to the output
  (unless `--no-copy-images` is given); files already in that folder are never
  overwritten, a different graphic of the same name gets a new name. A crafted MIF file
  can therefore make the converters copy any readable file from your computer next to the
  output, where you might publish it by mistake. mif2rtf does not copy graphics; it
  **embeds** every PNG and JPEG file it finds into the RTF itself, so a crafted MIF file can
  put such files from your computer into the RTF you pass on.
- **`include` statements read other files.** MIF's `include (pathname)` inserts another
  file, relative or absolute, into the MIF text before it is read (up to 10 levels deep).
  Its content can end up in the output.
- **The output is processed by other programs.** The Markdown and AsciiDoc the converters
  write is meant for pandoc, Asciidoctor and similar tools. Text from the MIF file is
  escaped so that it cannot become markup or directives (for example AsciiDoc
  `include::`, raw HTML in Markdown); graphics are referenced by the copied file names. In
  RTF, text is escaped so that it cannot become control words, groups or fields.
  If you find a way around this escaping, please report it as above.
- **Large inputs.** MIF files and the output are processed in memory; there are no size
  limits.

Convert untrusted files in a folder or container that holds nothing private, and check
the `images/` folder before you publish the output.

The converters never run code contained in a MIF file, do not use the network, and do
not start other programs.
