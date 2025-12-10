import argparse
import sys

from src.datascrubber.scrubbing import AccountScrubber, ContactScrubber
from src.datascrubber.settings import configure_logging, load_settings


def main():
    """Main entry point for the data scrubbing application."""
    logger = configure_logging()
    parser = argparse.ArgumentParser(description="Scrub lists against static Salesforce data.")
    subparsers = parser.add_subparsers(dest="scrub_type", required=True)

    parser_account = subparsers.add_parser("account", help="Run the account scrub.")
    parser_account.add_argument("filename", type=str, help="The Excel file to scrub (without .xlsx).")

    parser_contact = subparsers.add_parser("contact", help="Run the contact scrub.")
    parser_contact.add_argument("filename", type=str, help="The account scrub OUTPUT file to use.")

    args = parser.parse_args()

    try:
        settings = load_settings("config.ini")
    except Exception as exc:  # Provide a clean exit with context
        logger.error("Failed to load configuration", extra={"error": str(exc)})
        raise

    if args.scrub_type == "account":
        scrubber = AccountScrubber(settings, args.filename)
    else:
        scrubber = ContactScrubber(settings, args.filename)

    scrubber.run()


if __name__ == "__main__":
    main()
