# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.


from logging import INFO, basicConfig, getLogger

from bugbug import bugzilla
from bugbug.bug_snapshot import rollback

basicConfig(level=INFO)
logger = getLogger(__name__)


def test_bug_snapshot():
    for i, bug in enumerate(bugzilla.get_bugs()):
        logger.info(bug["id"])
        logger.info(i)

        rollback(bug, do_assert=True)
