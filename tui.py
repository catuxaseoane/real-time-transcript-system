"""
Textual-based live transcript TUI — subtitle style.

Each paragraph is a separate widget that updates in-place as words
and refinements arrive, just like live captions building up on screen.

Run with:
    uvicorn server:app &
    python tui.py
"""
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Header, Footer, Static

from poller import poll
from transcript.state import StreamState


def _label(raw_id: str | None) -> str:
    """Display speaker with 1-indexed convention."""
    if raw_id is None:
        return "Unknown"
    return f"Speaker {int(raw_id) + 1}" 

def _para_start(p) -> float:
    """Earliest word start time — used to sort paragraphs chronologically."""
    return min(w.start for w in p.words) if p.words else 0.0


class TranscriptApp(App):
    CSS = """
    VerticalScroll {
        height: 1fr;
        padding: 0 2;
    }

    .para {
        padding: 0 0 1 0;
    }

    #status {
        height: 1;
        background: $panel;
        content-align: center middle;
        color: $text-muted;
    }
    """

    BINDINGS = [("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield VerticalScroll(id="scroll")
        yield Static("● Connecting…", id="status")
        yield Footer()

    async def on_mount(self) -> None:
        self.state = StreamState()
        # paragraph_id → (widget_id, last_snapshot) so we know what changed
        self._para_state: dict[str, tuple[str, str]] = {}
        self._para_counter: int = 0

        self.run_worker(poll(self.state), exclusive=True)
        self.set_interval(0.3, self._refresh_display)

    def _refresh_display(self) -> None:
        scroll     = self.query_one("#scroll", VerticalScroll)
        status_bar = self.query_one("#status", Static)

        # ── Status bar with byte counter ──────────────────────────────────
        kb = self.state.byte_offset / 1024
        size = f"{kb:.1f} KB" if kb >= 1 else f"{self.state.byte_offset} B"
        if self.state.status == "live":
            status_bar.update(f"● Live  ·  {size} received")
        elif self.state.status == "ended":
            status_bar.update(f"■ Ended  ·  {size} received")

        # ── One Static widget per paragraph, updated in-place ─────────────
        # Sort chronologically — paragraph-insert can leave paragraphs in
        # non-chronological order in state.paragraphs.
        visible = sorted(
            (p for p in self.state.paragraphs if p.text().strip()),
            key=_para_start,
        )
        new_paragraph_added = False

        for i, p in enumerate(visible):
            text  = p.text().strip()
            label = _label(p.speaker())

            # Only show the speaker label when the speaker changes
            prev_label = _label(visible[i - 1].speaker()) if i > 0 else None
            show_label = label != prev_label

            markup   = f"[bold cyan]{label}:[/bold cyan] {text}" if show_label else f"  {text}"
            snapshot = f"{show_label}|{label}|{text}"  # includes show_label so we re-render if order changes

            if p.paragraph_id not in self._para_state:
                wid = f"para{self._para_counter}"
                self._para_counter += 1
                self._para_state[p.paragraph_id] = (wid, snapshot)
                scroll.mount(Static(markup, id=wid, classes="para"))
                new_paragraph_added = True
            else:
                wid, last_snapshot = self._para_state[p.paragraph_id]
                if snapshot != last_snapshot:
                    self._para_state[p.paragraph_id] = (wid, snapshot)
                    self.query_one(f"#{wid}", Static).update(markup)

        # Auto-scroll to bottom only when new paragraphs appear
        if new_paragraph_added:
            scroll.scroll_end(animate=False)


if __name__ == "__main__":
    app = TranscriptApp()
    app.run()