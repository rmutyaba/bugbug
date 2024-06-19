import json
import logging
import os

from libmozdata.phabricator import PhabricatorAPI

from bugbug.tools.code_review import PhabricatorReviewData
from bugbug.utils import get_secret

review_data = PhabricatorReviewData()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

os.makedirs("patches", exist_ok=True)
os.makedirs("comments", exist_ok=True)
os.makedirs("dataset", exist_ok=True)


class NoDiffsFoundException(Exception):
    def __init__(self, patch_id):
        super().__init__(f"No diffs found for the given patch ID: {patch_id}")
        self.patch_id = patch_id


class NoTransactionsFoundException(Exception):
    def __init__(self, patch_id):
        super().__init__(f"No transactions found for the given patch ID: {patch_id}")
        self.patch_id = patch_id


class NoDiffFoundForPHIDException(Exception):
    def __init__(self, phid):
        super().__init__(f"No diff found for PHID {phid}")
        self.phid = phid


class PhabricatorClient:
    def __init__(self):
        self.api = PhabricatorAPI(get_secret("PHABRICATOR_TOKEN"))

    def find_revision_from_patch(self, patch_id):
        diffs = self.api.search_diffs(diff_id=patch_id)

        if not diffs:
            raise NoDiffsFoundException(patch_id)

        revision_phid = diffs[0]["revisionPHID"]
        return revision_phid

    def find_transactions_from_patch(self, patch_id):
        revision_phid = self.find_revision_from_patch(patch_id)
        transactions = self.api.request(
            "transaction.search", objectIdentifier=revision_phid
        )["data"]

        if not transactions:
            raise NoTransactionsFoundException(patch_id)

        return transactions

    def get_diff_info_from_phid(self, phid):
        diffs = self.api.search_diffs(diff_phid=phid)
        if not diffs:
            raise NoDiffFoundForPHIDException(phid)
        return diffs[0]["id"], diffs[0]["revisionPHID"]

    def find_bugid_from_revision_phid(self, phid):
        revision = self.api.load_revision(rev_phid=phid)
        return revision["fields"]["bugzilla.bug-id"]


def download_inline_comments():
    for patch_id, comments in review_data.get_all_inline_comments(lambda c: True):
        save_comments_to_file(patch_id, comments)
    return


def save_comments_to_file(patch_id, comments):
    resolved_comments = [comment for comment in comments if comment.is_done]

    file_path = f"comments/{patch_id}.json"
    if os.path.exists(file_path) or not resolved_comments:
        return

    with open(file_path, "w") as f:
        json.dump([comment.__dict__ for comment in resolved_comments], f, indent=4)


def find_recent_update(transactions, comment_date_modified):
    updates = [
        transaction
        for transaction in transactions
        if transaction["type"] == "update"
        and transaction["dateModified"] <= comment_date_modified
    ]
    if not updates:
        return None
    most_recent_update = max(
        updates, key=lambda transaction: transaction["dateModified"]
    )
    return most_recent_update


def save_to_dataset(data):
    dataset_file = "dataset/inline_comment_dataset.json"
    with open(dataset_file, "a") as f:
        f.write(json.dumps(data) + "\n")


def to_int(value):
    if not value:
        return None
    if not isinstance(value, int):
        return int(value)
    return value


def process_comments(patch_threshold, diff_length_threshold):
    client = PhabricatorClient()
    comments_dir = "comments"
    patch_count = 0
    for file_name in os.listdir(comments_dir):
        file_path = os.path.join(comments_dir, file_name)
        with open(file_path, "r") as f:
            patch_id = int(file_name.replace(".json", ""))
            transactions = client.find_transactions_from_patch(patch_id)

            comments = json.load(f)
            for comment in comments:
                comment_date_modified = comment["date_modified"]
                most_recent_update = find_recent_update(
                    transactions, comment_date_modified
                )
                if not most_recent_update:
                    continue

                fix_patch_id, revision_phid = client.get_diff_info_from_phid(
                    most_recent_update["fields"]["new"]
                )

                # If the most recent patch is the original patch itself, skip it
                if fix_patch_id == patch_id:
                    continue

                bug_id = client.find_bugid_from_revision_phid(phid=revision_phid)
                review_data.load_patch_by_id(fix_patch_id)

                with open(f"patches/{fix_patch_id}.patch", "r") as f:
                    patch_diff = f.read()

                if len(patch_diff) > diff_length_threshold:
                    continue

                data = {
                    "bug_id": to_int(bug_id),
                    "revision_phid": revision_phid,
                    "initial_patch_id": to_int(patch_id),
                    "fix_patch_id": to_int(fix_patch_id),
                    "comment": comment,
                    "fix_patch_diff": patch_diff,
                }
                save_to_dataset(data)

        patch_count += 1
        if patch_count >= patch_threshold:
            break


if __name__ == "__main__":
    download_inline_comments()
    process_comments(patch_threshold=250, diff_length_threshold=5000)
