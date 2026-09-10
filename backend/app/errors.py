"""Typed operational errors which the API can turn into useful messages."""


class MealPlannerError(RuntimeError):
    pass


class PriceProviderError(MealPlannerError):
    pass


class PriceProviderAuthenticationError(PriceProviderError):
    pass


class PriceProviderRateLimitError(PriceProviderError):
    pass


class PriceProviderAccessChallengeError(PriceProviderError):
    """The provider returned a CAPTCHA/WAF/human-verification challenge."""


class IncompleteBasketError(MealPlannerError):
    pass
