from .example import ExampleProvider
from .concafe import ConCafeProvider

registry = {
    "example": ExampleProvider,
    "concafe": ConCafeProvider,
}
