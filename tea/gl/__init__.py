"""GL integration — posting through python-accounting ONLY (REQ-DATA-0022).

The library owns the gl schema and the double-entry invariant; the Package never
INSERTs into gl tables directly and never sums ledger rows for an authoritative
figure (REQ-DATA-0202). It composes the library's transaction subtypes and reads
its computed balances/reports.
"""
