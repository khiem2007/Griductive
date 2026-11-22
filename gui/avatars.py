"""Decorative portraits derived only from public character information."""

from __future__ import annotations

from hashlib import sha256

import pygame


class AvatarRenderer:
    """Draw consistent illustrated characters without external image assets."""

    def __init__(self) -> None:
        self._cache: dict[tuple[str, int], pygame.Surface] = {}

    def render(self, identity: str, size: int) -> pygame.Surface:
        """Return a portrait whose appearance is independent of hidden answers."""

        key = (identity, size)
        if key in self._cache:
            return self._cache[key]
        seed = sha256(identity.encode("utf-8")).digest()
        long_hair = bool(seed[0] % 2)
        skin = ((248, 205, 170), (218, 164, 119), (165, 110, 79), (238, 183, 145))[seed[1] % 4]
        hair = ((49, 37, 39), (93, 57, 42), (188, 131, 63), (51, 48, 68))[seed[2] % 4]
        shirt = ((88, 130, 202), (201, 103, 134), (104, 161, 143), (180, 132, 207))[seed[3] % 4]
        backdrop = ((208, 224, 244), (239, 218, 225), (220, 232, 217), (231, 222, 245))[seed[4] % 4]
        canvas = pygame.Surface((160, 160), pygame.SRCALPHA)
        pygame.draw.circle(canvas, backdrop, (80, 80), 79)
        if long_hair:
            pygame.draw.ellipse(canvas, hair, (37, 20, 86, 122))
        pygame.draw.ellipse(canvas, shirt, (24, 116, 112, 81))
        pygame.draw.rect(canvas, skin, (68, 101, 24, 29), border_radius=8)
        pygame.draw.polygon(canvas, (244, 240, 230), [(61, 119), (80, 132), (68, 142), (53, 124)])
        pygame.draw.polygon(canvas, (244, 240, 230), [(99, 119), (80, 132), (92, 142), (107, 124)])
        pygame.draw.ellipse(canvas, skin, (39, 65, 15, 22))
        pygame.draw.ellipse(canvas, skin, (106, 65, 15, 22))
        pygame.draw.ellipse(canvas, skin, (47, 32, 66, 82))
        pygame.draw.ellipse(canvas, hair, (43, 22, 74, 43))
        if long_hair:
            pygame.draw.polygon(canvas, hair, [(47, 46), (45, 92), (57, 65), (84, 43)])
            pygame.draw.polygon(canvas, hair, [(83, 38), (106, 85), (114, 59), (104, 35)])
        else:
            pygame.draw.polygon(canvas, hair, [(46, 49), (55, 19), (72, 28), (97, 18), (113, 49)])
        for eye_x in (66, 94):
            pygame.draw.line(canvas, hair, (eye_x - 5, 68), (eye_x + 4, 67), 2)
            pygame.draw.ellipse(canvas, (45, 40, 48), (eye_x - 3, 74, 6, 8))
            pygame.draw.circle(canvas, (255, 255, 255), (eye_x - 1, 76), 1)
        pygame.draw.line(canvas, (177, 115, 93), (80, 82), (78, 90), 2)
        pygame.draw.arc(canvas, (133, 68, 67), (70, 88, 21, 13), 3.3, 6.1, 2)
        if long_hair:
            for ear_x in (45, 114):
                pygame.draw.circle(canvas, (248, 200, 87), (ear_x, 88), 3)
        # Crop the shoulders to the round backdrop before scaling with antialiasing.
        mask = pygame.Surface((160, 160), pygame.SRCALPHA)
        pygame.draw.circle(mask, (255, 255, 255, 255), (80, 80), 79)
        canvas.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        portrait = pygame.transform.smoothscale(canvas, (size, size))
        if len(self._cache) >= 256:
            self._cache.clear()
        self._cache[key] = portrait
        return portrait
