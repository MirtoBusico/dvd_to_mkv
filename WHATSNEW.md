# What's new

## 2026-11-15

- Fixed missing language labels in newly copied Blu-ray MKVs: audio and subtitle
  tracks now keep the disc's three-letter language codes, matched by stream PID.
  This works with selected tracks, copy-all, and shared-PID companion tracks.
- Missing disc language codes produce a warning rather than guessed labels.
  Invalid language metadata stops the copy instead of repeatedly recopying it.
  Existing MKVs are not repaired, and original M2TS output is unchanged.
- The Manjaro/Arch package has been rebuilt as `2026.11.15-1`.

## 2026-11-14

The November 14 update brings new ways to inspect and verify discs,
lots of bug squashing, and improvements to GUI reliability and copying safety.

### New tools and controls

- **Verify Copy** compares an existing MKV or M2TS with a reference copied
  from the original source. It is optional, rereads the source, and needs
  temporary disk space. A failed check does not necessarily mean the copy is
  corrupt.
- **Preview** plays directly from a DVD or a selected Blu-ray playlist using
  FFplay. It does not apply the copy's track selection or provide 3D playback.
- The GUI discovers optical drives and offers a refresh action after disc
  changes. It does not automatically select a drive.
- **Clear All** resets the workspace while keeping saved profiles and source
  choices.
- A Manjaro/Arch package is included, with an application-menu entry.

### More reliable workflows

- Preference loading and saving run in the background. The GUI reports errors
  and offers choices if loading or shutdown takes longer than expected.
- Source detection, inspection, copying, and shutdown handle cancellation and
  stale results more carefully. Stalled filesystem helpers can be abandoned
  after forced termination; cleanup may be delayed.
- Drive refresh, reinspections, and profile changes handle saved and pending
  selections more consistently. Changes from a previous disc are not reused
  merely because a different disc was inserted into the same drive.
- Wide pane handles prevent divider drag areas from intercepting clicks on
  nearby controls.
- The GUI rejects symbolic links inside DVD and Blu-ray disc folders as well
  as links to the source itself. Links to optical devices remain supported.

### Safer copying and verification

- Verification stages its temporary reference beside the existing copy by
  default, so the copier checks space on that filesystem. Set `TMPDIR` to use
  a different staging filesystem.
- Before copying, the CLI checks that the output filesystem supports hard
  links and that GNU `sync` supports filesystem flushing. It flushes published
  output before reporting success; existing files are still not overwritten.
- Blu-ray key databases must be owned by the current user or root and have
  no group or other permissions.

Physical optical-drive and encrypted-disc testing, and full-movie 3D
playback validation, remain outstanding.

## 2026-11-10

Saved profiles, remembered track choices, and better handling of Blu-ray
chapters and 3D discs, along with a good round of fixes.

### Less setting things up from scratch

- Save profiles with your preferred audio and subtitle languages, Blu-ray
  output format, and minimum playlist length.
- The app remembers your profile and track choices for each disc or source,
  so you don't have to pick everything again next time. Output locations
  aren't saved.
- New lists start with nothing selected unless you've saved choices or your
  profile matches tracks by language. Use Select All when you want everything.
- Refreshing a Blu-ray's track list now brings back saved choices that
  were hidden because the list was too long. Tracks you deliberately
  unchecked stay unchecked.

### Blu-ray chapters and 3D

- Blu-ray MKVs keep the playlist's chapter markers, even when you only copy
  some tracks. Original M2TS copies get a separate chapter file alongside
  the video; whether it works depends on your player.
- Choose Automatic, MKV, or original M2TS for Blu-rays. Automatic keeps
  original M2TS when it detects the disc's 3D video, rather than losing
  the extra view. Original M2TS copies include all tracks.
- For now, 3D stays in M2TS while we wait for FFmpeg/mkvmerge to catch up
  with reliable Blu-ray 3D (MVC) remuxing to MKV in this workflow.
- Fixed a case where a normal timing reset on a 3D Blu-ray could make
  Automatic output choose MKV and lose the 3D part. Converting these
  playlists to 3D MKV isn't supported yet.
- Switching profiles now asks again before copying all tracks to original
  M2TS, rather than silently ignoring your track choices.
- That warning also catches tracks hidden by the display limit, even if
  you've selected every track you can see.

### Safer copying

- Fixed a security issue in shared output folders: someone with access to
  such a folder could redirect a copy and cause another file to be overwritten.
  Copying now stays tied to the folder it started in, and folders with unsafe
  ownership or permissions are refused. This needs Linux with `/proc` available.
- Gave the copier and its supporting code another security check. No new
  vulnerabilities were confirmed, and all tests and extra security checks
  passed, including checks with GTK and the Avatar disc image. That isn't a
  guarantee: attacks from a separate user account, other filesystem types,
  and security bugs in external tools weren't tested.

## 2026-10-31

A bit of tidying up and quite a few fixes. No big new features this time.

### Things that should behave better now

- Fixed a nasty one in the command-line script: `--retries 08` could leave
  you with a failed copy saved as if everything had worked. Leading zeros
  are now handled properly, and very long retry values are rejected.
- Selecting the same stream twice using different spellings, such as `1`
  and `01`, is now caught. The same goes for playlists and Blu-ray PIDs.
- DVD folders and key database files with names starting with a dash no
  longer get mistaken for command options.
- Changing the source quickly no longer starts detection for the old one.
  Closing the window also waits for the background workers to finish stopping.
- If inspecting a playlist's tracks fails, your previous selection stays put.
- The Activity pane no longer pulls you back to the bottom while you're
  reading earlier output. Very long lines are broken up to stop GTK from
  eating memory.
- Error messages are a little clearer, and unexpected errors leave more
  detail in Activity.

### A few extra checks

- Detection now looks for the actual DVD or Blu-ray marker files, rather
  than trusting a folder name.
- Added limits on track lists and labels, stricter checks on stream IDs,
  and filtering for control characters and text-direction tricks.
- The GUI won't accept symbolic links as sources or disc marker files.
  Device links such as `/dev/cdrom` are still fine.

### Worth knowing

- A reminder for encrypted Blu-rays: keep `~/.config/aacs/` at `700` and
  `KEYDB.cfg` at `600`. The script checks the file's permissions even when
  it finds it automatically, not just when you use `--keydb`. The folder
  permissions are a recommendation, not a check. This isn't new behaviour,
  just something worth spelling out.
- Automatic detection of images and devices now needs `prlimit`, from
  util-linux, as well as `7z` or `7zz`. It limits the probe's virtual address
  space to 512 MiB, not its physical RAM use. Without these tools, you can
  still choose DVD or Blu-ray yourself.
- For command-line use, stream indexes and retry counts accept 1-4 digits
  (0-9999), and playlist IDs accept 1-5 digits (0-99999). Leading zeros are
  fine within those lengths; the numbers are read as decimal.
- Blu-ray PIDs must be between `0x0000` and `0x1fff`.
