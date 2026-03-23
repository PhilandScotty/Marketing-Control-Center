"""Daily status export — writes MCC-STATUS.md to the Grindlab project directory."""
import logging
import os

logger = logging.getLogger("mcc.status_export")

OUTPUT_PATH = os.path.expanduser("~/clawd/projects/grindlab/MCC-STATUS.md")


def _run_export():
    """Generate and write the status markdown file."""
    # Import here to avoid circular imports at module level
    from manage import get_status_data, render_markdown

    data = get_status_data()
    if not data:
        logger.warning("No project found — skipping status export")
        return

    md = render_markdown(data)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        f.write(md)

    logger.info(f"Status export written to {OUTPUT_PATH}")


def status_export_job():
    """APScheduler-compatible wrapper."""
    try:
        _run_export()
    except Exception as e:
        logger.error(f"Status export failed: {e}")
