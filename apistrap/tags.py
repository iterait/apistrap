from dataclasses import dataclass
from typing import Optional


@dataclass
class TagData:
    name: str
    description: Optional[str] = None

    def to_dict(self):
        result = {"name": self.name}

        if self.description is not None:
            result["description"] = self.description

        return result
