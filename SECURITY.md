# Security policy

## Reporting a vulnerability

Please report security problems privately, not in a public issue: use **"Report a
vulnerability"** on the repository's *Security* tab (GitHub's private vulnerability
reporting). Include a MIF file or steps that show the problem if you can.

You can expect a first answer within two weeks. This is a small spare-time project,
so fixes may take longer; the report stays private until a fix is available.

## Supported versions

Only the latest version on `main` receives fixes.

## What to be aware of when converting untrusted files

mif2md and mif2adoc read MIF files and the files they refer to. Treat a MIF file from an
unknown source like any other untrusted document:

- **Referenced files are read from anywhere.** A MIF file names its imported graphics by
  path, and the converters follow relative paths (including `../`) and absolute paths.
  Graphics that are found are **copied** into the `images/` folder next to the output
  (unless `--no-copy-images` is given); files already in that folder are never
  overwritten, a different graphic of the same name gets a new name. A crafted MIF file
  can therefore make the converters copy any readable file from your computer next to the
  output, where you might publish it by mistake.
- **`include` statements read other files.** MIF's `include (pathname)` inserts another
  file, relative or absolute, into the MIF text before it is read (up to 10 levels deep).
  Its content can end up in the output.
- **The output is processed by other programs.** The Markdown and AsciiDoc the converters
  write is meant for pandoc, Asciidoctor and similar tools. Text from the MIF file is
  escaped so that it cannot become markup or directives (for example AsciiDoc
  `include::`, raw HTML in Markdown); graphics are referenced by the copied file names.
  If you find a way around this escaping, please report it as above.
- **Large inputs.** MIF files and the output are processed in memory; there are no size
  limits.

Convert untrusted files in a folder or container that holds nothing private, and check
the `images/` folder before you publish the output.

The converters never run code contained in a MIF file, do not use the network, and do
not start other programs.
