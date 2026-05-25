from pydantic import ConfigDict


def to_camel(value: str) -> str:
    chunks = value.split("_")
    return chunks[0] + "".join(chunk.title() for chunk in chunks[1:])


def get_camel_case_config(**extra_kwargs: object) -> ConfigDict:
    return ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        use_enum_values=True,
        **extra_kwargs,
    )
