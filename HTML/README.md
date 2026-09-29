# HTML/ - optional static assets for linbpq's web server

linbpq's HTTP server (on `HTTPPORT`) builds its pages from templates
compiled into the binary. It also serves any file you put in an
`HTML/` directory next to `bpq32.cfg`, which is how these assets get
used.

## What's here

- `favicon.ico` - site icon (8x8 BPQ icon from upstream
  NodePages.zip, 2011 vintage).
- `background.jpg` - page background, referenced by the
  `<body background="/background.jpg">` tag in many pages.

Both are optional. Without them the browser renders the pages
plainly.

### `samples/` - alternative front pages

Optional hand-written replacements for the dynamically-generated
front pages. If you drop one into the parent `HTML/` directory,
linbpq's `SendMessageFile` serves it instead of the built-in page:

- `index.html` - front page (with APRS link).
- `indexnoaprs.html` - front page when APRS isn't running.
- `NodeMenu.html` - top-nav for `/Node/*` pages. The built-in menu
  is richer: it adds Mail / Chat / driver entries based on what's
  enabled.

These were originally distributed as
[NodePages.zip](https://www.cantab.net/users/john.wiseman/Documents/Samples/NodePages.zip)
on John Wiseman's site (2012). Strings of the form `##MY_CALLSIGN##`
get substituted at serve time by `HTTPcode.c::ReplaceVariables`.

## Upstream

Authoritative documentation:
[BPQWebServer.html](https://www.cantab.net/users/john.wiseman/Documents/BPQWebServer.html)
on John Wiseman's site.
