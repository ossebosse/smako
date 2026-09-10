from pydantic import BaseModel, ConfigDict, Field


def validated_catalog_page(
    payload: object,
    *,
    requested_page: int | None = None,
) -> tuple[list[object], int]:
    """Validate traversal metadata, including Willys' proven terminal null sentinel.

    A ``null`` results value is accepted only for the final logical page when
    pagination proves that the requested offset equals the total result count.
    This keeps replay and live traversal fail-closed for every other null shape.
    """

    if not isinstance(payload, dict):
        raise TypeError("Willys catalog page must be an object")
    pagination = payload.get("pagination")
    if not isinstance(pagination, dict):
        raise TypeError("Willys catalog page pagination must be an object")
    current_page = pagination.get("currentPage")
    number_of_pages = pagination.get("numberOfPages")
    if (
        isinstance(current_page, bool)
        or not isinstance(current_page, int)
        or isinstance(number_of_pages, bool)
        or not isinstance(number_of_pages, int)
    ):
        raise TypeError("Willys pagination fields must be explicit integers")
    if number_of_pages < 1 or current_page < 0 or current_page >= number_of_pages:
        raise ValueError("Willys pagination bounds are invalid")
    if requested_page is not None and current_page != requested_page:
        raise ValueError("Willys pagination did not return the requested page")

    if "results" not in payload:
        raise TypeError("Willys catalog page results field is missing")
    results = payload.get("results")
    if isinstance(results, list):
        return results, number_of_pages
    if results is not None:
        raise TypeError("Willys catalog page results must be a list")

    page_size = pagination.get("pageSize")
    total_results = pagination.get("totalNumberOfResults")
    terminal_null = (
        not isinstance(page_size, bool)
        and isinstance(page_size, int)
        and page_size > 0
        and not isinstance(total_results, bool)
        and isinstance(total_results, int)
        and total_results >= 0
        and current_page == number_of_pages - 1
        and total_results == current_page * page_size
    )
    if not terminal_null:
        raise TypeError("Willys null results lacked terminal-page consistency evidence")
    return [], number_of_pages


class WillysCatalogPage(BaseModel):
    model_config = ConfigDict(extra="allow")

    results: list[dict] | None = Field(default_factory=list)
    pagination: dict = Field(default_factory=dict)
    categoryInfo: dict = Field(default_factory=dict)
    breadcrumbs: list[dict] = Field(default_factory=list)


class WillysCategoryNode(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    title: str
    url: str
    valid: bool = True
    children: list["WillysCategoryNode"] = Field(default_factory=list)

    def leaf_paths(self) -> list[str]:
        if not self.valid:
            return []
        if not self.children:
            return [self.url.strip("/")] if self.url and self.id != "N00" else []
        result: list[str] = []
        for child in self.children:
            result.extend(child.leaf_paths())
        return result
