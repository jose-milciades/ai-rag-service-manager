"""Infrastructure layer conventions.

Subcapas vigentes:

- ``clients``: SDKs y conexiones a sistemas externos o APIs remotas
- ``repositories``: implementaciones concretas de contratos del dominio
- ``vector_store``: adapters tecnicos y facades para backends vectoriales

Regla de uso:

- ``services`` consume infraestructura, pero no al reves
- ``domain`` define contratos; ``infrastructure`` los implementa
- ``core`` concentra configuracion transversal, no integraciones concretas
"""