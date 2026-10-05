# Раскадровка: битва с гоблинами на равнине у леса

Цель: 20 сек = 5 клипов по 4 сек. Сегодня только ключевые кадры (картинки). Анимация в другой модели позже.
Модель картинок: Animagine XL 4.0 (уже проверена, workspace/workflows/anime_sdxl_t2i.json). Формат тегов: Danbooru.
Стиль: современный dark fantasy. Размер 1216x832 (горизонталь, нативный SDXL bucket), уже выставлен в workflows/anime_sdxl_t2i.json.

## Локация (общий блок, вставлять в каждый кадр)
`grassland, forest edge, dark pine forest in background, overcast sky, dramatic storm clouds, golden hour rim light, mist, trampled grass, dust`

## Персонажи (общие блоки, вставлять дословно для консистентности)

**Рыцарь**: `1boy, knight, full plate armor, dark steel armor with gold trim, tattered red cape, closed great helm with visor slit, two-handed greatsword, zweihander, broad stance`

**Разбойница**: `1girl, rogue, agile, short silver hair, ponytail, green eyes, black leather armor, dark green hooded cloak, fingerless gloves, dual wielding, two short daggers, reverse grip, athletic`

**Монстры**: `goblins, orcs, green skin, crude armor, rusty weapons, fangs, pointed ears, snarling` (3-5 штук, лучше держать в кадре 2-3)

## Общий префикс качества
`masterpiece, high score, great score, absurdres, anime screencap, dark fantasy, cinematic lighting, detailed background`

## Негатив
`lowres, bad anatomy, bad hands, extra fingers, extra limbs, missing limbs, fused weapons, deformed sword, text, watermark, signature, blurry, jpeg artifacts, worst quality, low quality, cropped, 3boys, 2girls`

## Кадры

| # | Время | Кадр | Продолжение |
|---|---|---|---|
| 1 | 0-4 c | Establishing: общий план, оба героя спиной/в профиль, на них идут гоблины из леса | по первому кадру |
| 2 | 4-8 c | Рыцарь замахивается двуручником, 2 гоблина перед ним, средний план | по первому кадру |
| 3 | 8-12 c | Разбойница в прыжке с кинжалами над гоблином, низкий ракурс, динамика | по последнему кадру клипа 2 если нужно |
| 4 | 12-16 c | Спина к спине, окружены гоблинами, крупнее план обоих | по первому кадру |
| 5 | 16-20 c | Финал: рыцарь рубит, разбойница рядом, гоблины отступают, пыль, героический ракурс | по последнему кадру клипа 4 |

### Промты

**1. Establishing**
`masterpiece, high score, great score, absurdres, anime screencap, dark fantasy, cinematic lighting, wide shot, from behind, 1boy, knight, full plate armor, dark steel armor with gold trim, tattered red cape, closed great helm, two-handed greatsword, 1girl, rogue, short silver hair, ponytail, black leather armor, dark green hooded cloak, two short daggers, standing side by side, goblins, orcs, green skin, crude armor, running out of forest, grassland, forest edge, dark pine forest, overcast sky, storm clouds, mist`

**2. Рыцарь**
`masterpiece, high score, great score, absurdres, anime screencap, dark fantasy, cinematic lighting, medium shot, 1boy, knight, full plate armor, dark steel armor with gold trim, tattered red cape, closed great helm, two-handed greatsword, zweihander, swinging sword overhead, motion blur, speed lines, 2 goblins, green skin, crude armor, rusty weapons, snarling, grassland, forest edge, overcast sky, dust, golden rim light`

**3. Разбойница**
`masterpiece, high score, great score, absurdres, anime screencap, dark fantasy, cinematic lighting, low angle, dynamic angle, 1girl, rogue, short silver hair, ponytail, green eyes, black leather armor, dark green hooded cloak, dual wielding, two short daggers, reverse grip, jumping, midair, attacking, goblin, green skin, fangs, grassland, forest edge, dark pine forest, overcast sky, motion blur`

**4. Спина к спине**
`masterpiece, high score, great score, absurdres, anime screencap, dark fantasy, cinematic lighting, 1boy, 1girl, back-to-back, knight, full plate armor, dark steel armor with gold trim, tattered red cape, two-handed greatsword, rogue, short silver hair, ponytail, black leather armor, green hooded cloak, two short daggers, surrounded, goblins, orcs, green skin, crude armor, circle formation, grassland, forest edge, stormy sky, wind, dust`

**5. Финал**
`masterpiece, high score, great score, absurdres, anime screencap, dark fantasy, cinematic lighting, dramatic angle, 1boy, knight, full plate armor, tattered red cape, two-handed greatsword, slashing, 1girl, rogue, short silver hair, ponytail, black leather armor, green hooded cloak, two short daggers, fighting stance, goblins, defeated, retreating, fallen goblin, grassland, forest edge, sunset, golden hour, god rays, dust`

## Риски
- Консистентность персонажей между кадрами: Animagine без LoRA/IP-Adapter будет дрейфовать (шлем, цвет плаща, причёска). Лечится дословным блоком персонажа и фиксированным seed. Для сильной консистентности нужен IP-Adapter или Flux Kontext.
- Двуручный меч и два кинжала: частые артефакты (слитое оружие, лишние руки). Генерировать по 4-6 вариантов на кадр и выбирать.
- Закрытый шлем рыцаря нарочно: не нужно держать лицо одинаковым.
- Толпа монстров лучше держать 2-3 в кадре: 5 в одном кадре даст кашу.
