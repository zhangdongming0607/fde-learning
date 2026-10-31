"""Shared immutable reads for natural-language knowledge and its precheck."""
from .interview_extraction import Workspace, ExtractionModel, require

class SnapshotReader(Workspace):
    def __init__(self, root):
        super().__init__(root)
        self.files = {}
    def raw(self, rel):
        self.path(rel)
        if rel not in self.files:
            self.files[rel] = super().raw(rel)
            require(len(self.files) <= 500 and sum(map(len, self.files.values())) <= 16_000_000,
                    'SOURCE_BUDGET_EXCEEDED')
        return self.files[rel]

class AuditWorkspace(Workspace):
    def __init__(self, root):
        super().__init__(root)
        self.files = {}
        self.size = 0
    def raw(self, rel):
        self.path(rel)
        if rel not in self.files:
            data = super().raw(rel)
            self.size += len(data)
            require(len(self.files) < 5000 and self.size <= 128_000_000, 'SOURCE_BUDGET_EXCEEDED')
            self.files[rel] = data
        return self.files[rel]

class ContextModel(ExtractionModel):
    """Use the extraction adapter's explicit profiles and request recording."""
