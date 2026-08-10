from dataclasses import dataclass, field
from typing import List, Dict, Any
import yaml

@dataclass
class UserState:
    customer_name: str = ""
    phone_number: str = ""
    address: str = ""
    cart: List[Dict[str, Any]] = field(default_factory=list)
    discount_applied: float = 0.0
    current_agent: str = "greeter"

    def get_subtotal(self) -> float:
        return sum(item["price"] * item["quantity"] for item in self.cart)

    def get_total(self) -> float:
        subtotal = self.get_subtotal()
        return round(subtotal * (1.0 - self.discount_applied), 2)

    def to_yaml(self) -> str:
        return yaml.dump({
            "customer_name": self.customer_name,
            "phone_number": self.phone_number,
            "address": self.address,
            "cart": self.cart,
            "subtotal": f"${self.get_subtotal():.2f}",
            "discount": f"{int(self.discount_applied * 100)}%",
            "total_due": f"${self.get_total():.2f}"
        })