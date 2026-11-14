# DVD and Blu-ray to MKV

Copy the bits you want from a DVD or Blu-ray into a video file, without
re-encoding. Pick the movie, audio, and subtitles, and leave the rest behind.

## What you'll need

This runs on Linux. Before starting, make sure you have:

- **Bash, FFmpeg and FFprobe** for copying and checking video.
- **Python 3, PyGObject and GTK 4** for the windowed app.
- **For DVDs:** an FFmpeg build with the `dvdvideo` input format.
  Not every packaged version includes it.
- **For Blu-rays:** `bluray_info`, `bluray_copy` and `jq`.
- **For automatic 3D detection:** FFprobe with Blu-ray protocol support.
- **For automatic disc detection:** `7z` or `7zz`, plus `prlimit` from
  util-linux. Without these, choose DVD or Blu-ray yourself.

Linux's `/proc` filesystem also needs to be available for safe copying.
Package names vary between distributions.

## Get started

Keep the included `dvdvideo/` folder beside the scripts, then run:

```sh
./dvd-to-mkv-gui.py
```

1. Choose your disc image, drive, or disc folder.
2. Let the app detect DVD or Blu-ray, or choose it yourself.
3. Inspect the disc and pick what to copy.
4. Choose where to save it and start copying.

The Activity pane tells you what's happening and shows any errors.
Existing output files won't be overwritten.

## Pick your tracks once

Save a profile with your favourite audio and subtitle languages, Blu-ray
output format, and minimum playlist length.

The app also remembers your choices for each source, so opening the same
disc again doesn't mean starting from scratch. You'll still need to choose
where to save the copy.

New lists start with nothing selected unless you have saved choices or your
profile picks matching tracks. Use **Select All** or **Select All Tracks**
when you want everything.

## MKV or M2TS?

For regular 2D video, MKV is the usual choice. Blu-rays offer three options:

- **Automatic:** uses MKV normally and keeps original M2TS when it detects
  Blu-ray 3D video.
- **MKV:** lets you choose which tracks to keep.
- **Original M2TS:** keeps all tracks, including both views of a 3D movie.
  You can't leave individual tracks out in this mode.

For now, 3D stays in M2TS while we wait for FFmpeg/mkvmerge to catch up with
reliable Blu-ray 3D copying to MKV in this workflow. Choosing MKV yourself
doesn't add 3D support.

Automatic detection only checks a sample. If you know a playlist is 3D but
it isn't detected, choose **Original M2TS** yourself. You'll need a player
that supports Blu-ray 3D; full-movie 3D playback hasn't been verified here.

## Chapters come along too

Blu-ray MKVs keep the playlist's chapter markers. M2TS copies get a separate
chapter file beside the video instead. Keep the two together, but bear in
mind that not every player reads that file, and seeking may be off on
playlists made from several clips.

## A few things worth knowing

- The suggested main movie is a hint, not a promise. The longest playlist
  can sometimes be a menu.
- Protected Blu-rays may need a local key database. Put `KEYDB.cfg` in
  `~/.config/aacs/` and keep it private: folder permissions `700`, file
  permissions `600`.
- Save into a folder you own. Unsafe shared output folders are refused.
- If the app rejects a shortcut to a disc image or folder, choose the real
  file or folder instead. Drive links such as `/dev/cdrom` are fine.

## Prefer the terminal?

Start with:

```sh
./dvd-to-mkv.sh --help
```

## More details

- [What's new](./WHATSNEW.md)

## Standards and primary references

These are the primary documents to consult when changing the formats, API
contracts, or operating-system behavior used by this application. They are
references for the implemented subset, not a claim that the application
conforms to every feature in each specification.

### DVD, UDF, and media formats

- [ECMA-167](https://ecma-international.org/publications-and-standards/standards/ecma-167/)
  specifies the underlying volume and file structures used by UDF. Consult it
  alongside the UDF profile actually being parsed.
- [ECMA TR/112: Universal Disk Format](https://ecma-international.org/publications-and-standards/technical-reports/ecma-tr-112/)
  is the current Ecma UDF reference. Part 1 describes the general format;
  Part 7 documents UDF 1.02. Use the other revision parts only when claiming
  support for those revisions. Disc filesystem reading is delegated to
  external tools; this repository does not include a UDF reader.
- [ECMA-267](https://ecma-international.org/publications-and-standards/standards/ecma-267/)
  describes the physical/data format of 120 mm DVD read-only discs. It does
  not replace the DVD-Video application-layer specification.
- **DVD-Video application layer:** DVD Forum, *DVD Specifications for
  Read-Only Disc, Part 3: Video Specifications*. This is the relevant
  reference for IFO/VOB navigation and DVD-Video structures; access is
  controlled. Do not treat ECMA-167 or ECMA-267 as a substitute.
- **Blu-ray Disc formats:** use the applicable Blu-ray Disc Association
  licensed specifications for claims about BD-ROM, playlist, transport-stream,
  or MVC conformance. The GUI delegates disc inspection and copying to
  `bluray_info`, `bluray_copy`, and FFmpeg; its MVC probe checks only the
  documented sample and NAL-unit subset, not full-disc conformance.
- [ISO/IEC 13818-1:2025 (MPEG-2 Systems)](https://www.iso.org/standard/91403.html)
  is a useful reference for MPEG transport/program streams used inside DVD and
  Blu-ray media. For AVC/MVC bitstream claims, consult the applicable
  [ISO/IEC 14496-10:2025](https://www.iso.org/standard/87574.html) edition.
  These standards describe the media formats; the application relies on
  FFmpeg and does not implement full decoders.

### GUI, runtime, and data interchange

- [GTK 4 API reference](https://docs.gtk.org/gtk4/) and [Gtk.Accessible.announce](https://docs.gtk.org/gtk4/method.Accessible.announce.html)
  define widget and accessibility API availability. `announce()` is available
  since GTK 4.14, so code using it must remain compatible with older supported
  GTK installations.
- [GLib main event loop](https://docs.gtk.org/glib/main-loop.html) and
  [GMainContext](https://docs.gtk.org/glib/struct.MainContext.html) document
  event-source lifetime, dispatch, and thread/context behavior. Use these when
  changing GTK-thread dispatch, timers, or worker completion notifications.
- Python typing references: [PEP 484](https://peps.python.org/pep-0484/)
  (type hints), [PEP 544](https://peps.python.org/pep-0544/)
  (protocols/structural subtyping), and
  [PEP 695](https://peps.python.org/pep-0695/) (type-parameter syntax used by
  the Python 3.14 code). These specify typing syntax and static-checker
  contracts, not runtime validation.
- [RFC 8259](https://www.rfc-editor.org/rfc/rfc8259) defines JSON used by
  preferences and isolated helper-process messages.
- [RFC 3629](https://www.rfc-editor.org/rfc/rfc3629) defines UTF-8, relevant
  to JSON text and paths/messages explicitly encoded as UTF-8. UDF compressed
  Unicode identifiers use the encoding rules in ECMA TR/112 instead.
- [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir/latest/)
  defines `$XDG_CONFIG_HOME`, used to locate GUI preferences.

### Linux and filesystem behavior

- [POSIX.1-2024 / The Open Group Base Specifications Issue 8](https://pubs.opengroup.org/onlinepubs/9799919799/)
  is the reference for portable file and process interfaces where the
  application relies on POSIX behavior.
- Linux-specific behavior is outside POSIX. Consult the relevant
  [Linux man-pages](https://man7.org/linux/man-pages/) for `/proc` descriptor
  paths, `memfd_create`, block-device ioctls, `fsync`, and related calls.
  Output pinning, block-device sizing, and subprocess argument spooling
  intentionally depend on Linux facilities.
