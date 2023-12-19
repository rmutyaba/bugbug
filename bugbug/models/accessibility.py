# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import logging

import xgboost
from imblearn.over_sampling import BorderlineSMOTE
from imblearn.pipeline import Pipeline as ImblearnPipeline
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction import DictVectorizer
from sklearn.pipeline import Pipeline

from bugbug import bug_features, bugzilla, feature_cleanup, utils
from bugbug.model import BugModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AccessibilityModel(BugModel):
    def __init__(self, lemmatization=False):
        BugModel.__init__(self, lemmatization)

        self.calculate_importance = False

        feature_extractors = [
            bug_features.HasSTR(),
            bug_features.Keywords({"access"}),
            bug_features.HasAttachment(),
            bug_features.Product(),
            bug_features.FiledVia(),
            bug_features.HasImageAttachmentAtBugCreation(),
        ]

        cleanup_functions = [
            feature_cleanup.fileref(),
            feature_cleanup.url(),
            feature_cleanup.synonyms(),
        ]

        self.extraction_pipeline = Pipeline(
            [
                (
                    "bug_extractor",
                    bug_features.BugExtractor(
                        feature_extractors,
                        cleanup_functions,
                        rollback=True,
                    ),
                ),
            ]
        )

        self.clf = ImblearnPipeline(
            [
                (
                    "union",
                    ColumnTransformer(
                        [
                            ("data", DictVectorizer(), "data"),
                            ("title", self.text_vectorizer(min_df=0.0001), "title"),
                            (
                                "first_comment",
                                self.text_vectorizer(min_df=0.0001),
                                "first_comment",
                            ),
                        ]
                    ),
                ),
                ("sampler", BorderlineSMOTE(random_state=0)),
                (
                    "estimator",
                    xgboost.XGBClassifier(n_jobs=utils.get_physical_cpu_count()),
                ),
            ]
        )

    @staticmethod
    def __is_accessibility_bug(bug):
        """Check if a bug is an accessibility bug."""
        return bug["cf_accessibility_severity"] != "---" or "access" in bug["keywords"]

    def get_labels(self):
        classes = {}

        for bug in bugzilla.get_bugs():
            bug_id = int(bug["id"])

            if "cf_accessibility_severity" not in bug:
                continue

            classes[bug_id] = 1 if self.__is_accessibility_bug(bug) else 0

        logger.info(
            "%d bugs are classified as non-accessibility",
            sum(label == 0 for label in classes.values()),
        )
        logger.info(
            "%d bugs are classified as accessibility",
            sum(label == 1 for label in classes.values()),
        )

        return classes, [0, 1]

    def get_feature_names(self):
        return self.clf.named_steps["union"].get_feature_names_out()

    def overwrite_classes(self, bugs, classes, probabilities):
        for i, bug in enumerate(bugs):
            if self.__is_accessibility_bug(bug):
                classes[i] = [1.0, 0.0] if probabilities else 1
        return classes
