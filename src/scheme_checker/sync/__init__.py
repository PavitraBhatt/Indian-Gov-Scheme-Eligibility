"""Scheme sync pipeline.

Pulls scheme data from an external government source, normalizes it to our
canonical schema (Claude-assisted), diffs it against the JSON database, and
writes proposed changes for a human to review via pull request.

Nothing here ever auto-publishes: the output is a proposal, gated on review.
"""
