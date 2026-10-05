# Plan: тестовая анимация ключевых кадров (Wan 2.2 I2V), RunPod Community

**Status: APPROVED by user ("запускай", 2026-10-05) for THIS run only.** Лимиты: $2/ч максимум, потолок плана $1.00 или 120 мин. Одобрение не переносится на следующие запуски.
Предыдущий план (ключевые кадры «бой в лесу дубль 2») сохранён в `workspace/archive/plan_boi_v_lesu_dubl_2_keyframes.md`.
Составлено 2026-10-05 model-selector-agent, обновлено оркестратором по ответам пользователя и проверке скриптов. Цены GPU взяты live через read-only GraphQL RunPod в тот же день и перед запуском перепроверяются.

## 1. Решения пользователя (зафиксированы)
- Тип: **I2V** (картинка -> видео), T2V не рассматривается.
- Входные кадры (4 шт., начала 4 сцен): `workspace/archive/бой_в_лесу_дубль_2/кадр_1.6.png`, `кадр_2.3.png`, `кадр_3.4.png`, `кадр_4.3.png` (1216x832).
- Клип: 480p, **704x480, 65 кадров @16 fps = 4.06 с** (пропорция 1.467 против 1.462 у кадров, обрезка не нужна; длина Wan должна быть 4n+1). Каждый клип от своего кадра, без цепочки.
- **2 seed на каждый кадр** (вариант A: 4 кадра x 2 seed = 8 клипов) плюс пробный клип.
- **A/B со 5B**: те же 4 кадра на TI2V-5B, 1 seed (4 клипа).
- **Интерполяция до 32 fps** (RIFE) для всех итоговых клипов; исходные 16 fps тоже сохраняются.
- GPU: **RTX 4090 24 GB** (цена сейчас $0.34/ч), запасная 3090 ($0.22/ч).
- **Лимит цены $2/ч действует только для видео**: он зашит как значение по умолчанию в `runpod_video.sh`; `.env` и CLAUDE.md не меняются, а `runpod.sh` остаётся с лимитом $0.25/ч.
- Бюджет теста: **$2-3 всего**; жёсткий внутренний потолок плана **$1.00 или 120 мин**, что наступит раньше.
- Промпты движения готовы: `workspace/prompts/built/wan_i2v_s01.txt` ... `s04.txt` (по одному на кадр 1.6, 2.3, 3.4, 4.3; POSITIVE + NEGATIVE + START_FRAME), заметка по Wan в `workspace/prompts/model_notes/wan-2.2-i2v.md`.

## 2. Что сейчас доступно (проверено 2026-10-05)
- Открытые веса Wan есть только до **Wan 2.2** (T2V/I2V-A14B, TI2V-5B, S2V, Animate, Fun-варианты). У Wan 2.5, 2.6, 2.7 и 3.0 открытых весов нет, они доступны только через платные API. Проверено по списку репозиториев `Wan-AI` на Hugging Face: под именами Wan2.5+ там только пустые репозитории-заглушки сторонних авторов. Один блог (runaihome.com) пишет, что веса 2.7 лежат на HF, это не подтверждается.
- Лицензия Wan 2.2 (A14B, 5B), LoRA lightx2v: Apache-2.0, коммерческое использование разрешено.
- В нативном ComfyUI есть всё нужное: Wan 2.2 I2V и TI2V, LoRA, сохранение в mp4 (`CreateVideo`/`SaveVideo`). Kijai WanVideoWrapper **не нужен**. Для GGUF-вариантов нужна только нода `city96/ComfyUI-GGUF`.

## 3. Сравнение вариантов (I2V, 704x480, ~4 с)
Время генерации — **оценки** по данным сообщества (4090: 5B 480p 5 с около 4 мин без ускорения; 14B без квантизации 480p 281 с; на 3090 в 1.5-2 раза медленнее, чем на 4090). Точную цифру даст пробный клип.

| # | Вариант | Файлы, GB | VRAM | GPU (Community, $/ч live) | Клип 4 с, мин (оценка) |
|---|---|---|---|---|---|
| **A** | **Wan2.2 I2V-A14B fp8_scaled + lightx2v 4-step LoRA**, нативно | **36.9** | ~16-20 (по одному эксперту за раз) + RAM 32+ | **RTX 4090 $0.34** / RTX 3090 $0.22 (сток Low) / A5000 $0.16 (нет в стоке) | 4090: 1.5-2; 3090: 2.5-4 |
| B | Wan2.2 TI2V-5B fp16, 20-30 шагов, нативно | 18.2 | 8-12 (с оффлоадом) | 4090 / 3090 / 3080 Ti 12GB $0.18 | 4090: 3-4 |
| B-Q8 | TI2V-5B GGUF Q8_0 (+ComfyUI-GGUF) | 13.6 | ~8 | 3080 Ti $0.18 | 5-7 |
| C | I2V-A14B GGUF Q4_K_M x2 + lightx2v (+ComfyUI-GGUF) | 28.6 | 12-16 | A4000 $0.17 (нет в стоке) / 4080 $0.27 | 5-7 |
| — | Wan2.1 I2V-480p-14B fp8 + clip_vision_h | 24.7 | 16-20 | 3090 | устарел, 2.2 лучше при той же цене |
| — | Wan2.1 Fun-InP 1.3B | ~10 | 8 | любая | дёшево, но качество для теста слабое |

Вывод: основная часть счёта — установка (~20 мин), а не генерация, поэтому берём лучшее качество (вариант A), а 4090 вместо 3090 ускоряет генерацию почти вдвое за +$0.12/ч.

## 4. Рекомендация
**Основной: вариант A** на **RTX 4090**: Wan 2.2 I2V-A14B fp8_scaled (high и low noise эксперты) + lightx2v 4-step I2V LoRA (версия 1022), нативный ComfyUI. **A/B: вариант B** (TI2V-5B fp16) на той же сессии на тех же 4 кадрах.
GPU-цепочка для этого запуска: **4090 -> 3090 -> A5000** (только карты с 24 GB). Она зашита в отдельном скрипте `runpod_video.sh` (лимит $2/ч, диск по умолчанию 100 GB, предупреждение при цене > $0.50/ч). `runpod.sh` не менялся и остаётся для не-видео задач (лимит $0.25/ч, цепочка с A4000/A4500, которая для варианта A не годится).
Network Volume **не нужен**: 55 GB x $0.07/GB-мес = ~$3.9 в месяц, это больше бюджета теста. Повторная загрузка весов ~$0.02 за сессию.
Датацентр не фиксируем: без volume под берёт любой DC, где карта есть (`create-pod-novol`).

## 5. Веса (строки для `workspace/scripts/models.manifest`)
Все URL проверены 2026-10-05: HTTP 200, токен HF не нужен, размеры сверены по `Content-Length`.
**Формат строки: `<subdir> <filename> <url>`, комментарий только отдельной строкой, начинающейся с `#`.** `download_models.sh` читает `read -r sub name url`, поэтому комментарий после URL в конце строки попал бы в URL.
```
# вариант A (36.94 GB): high 14.29, low 14.29, umt5 6.74, vae 0.25, loras 0.63 + 0.74
diffusion_models  wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors  https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors
diffusion_models  wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors   https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors
text_encoders     umt5_xxl_fp8_e4m3fn_scaled.safetensors            https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors
vae               wan_2.1_vae.safetensors                           https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors
loras             wan2.2_i2v_A14b_high_noise_lora_rank64_lightx2v_4step_1022.safetensors  https://huggingface.co/lightx2v/Wan2.2-Distill-Loras/resolve/main/wan2.2_i2v_A14b_high_noise_lora_rank64_lightx2v_4step_1022.safetensors
loras             wan2.2_i2v_A14b_low_noise_lora_rank64_lightx2v_4step_1022.safetensors   https://huggingface.co/lightx2v/Wan2.2-Distill-Loras/resolve/main/wan2.2_i2v_A14b_low_noise_lora_rank64_lightx2v_4step_1022.safetensors
# запасные LoRA (официальный репак Comfy-Org v1), только если 1022 даст "lora key not loaded": 1.23 GB x2
# loras  wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors  https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors
# loras  wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors   https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors
```
Вариант B кладётся в **отдельный** манифест `models_b.manifest` (18.15 GB; text encoder общий с A) и скачивается **после** того, как A готов и ComfyUI запущен (в фоне, вне 15-минутного окна провижининга):
```
# diffusion_models 10.00 GB, vae 1.41 GB
diffusion_models  wan2.2_ti2v_5B_fp16.safetensors  https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors
vae               wan2.2_vae.safetensors           https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan2.2_vae.safetensors
```
I2V-доп.: **CLIP-vision для Wan 2.2 не нужен**, ни для A14B, ни для 5B: картинка кодируется через VAE в `WanImageToVideo` / `Wan22ImageToVideoLatent`. Входные кадры — 4 PNG из `workspace/archive/бой_в_лесу_дубль_2/` (~1.2-1.5 MB каждый), загружаются через `/upload/image`.

## 6. Диск пода (важно)
По прошлому запуску на Community `/workspace` ~20 GB при любом запрошенном диске. 55 GB весов (A 37 + B 18) туда **не влезут**.
- Решение без правки кода: `create-pod-novol wan-i2v COMMUNITY 100` (container disk 100 GB), а на поде `WS=/root/ws` для `setup_comfyui.sh` и `MODELS_DIR=/root/ws/ComfyUI/models` для `download_models.sh`.
- Перед загрузкой гейт: `df -h /root` должен показать **≥ 75 GB** свободного (ComfyUI+venv+torch ~10 GB + веса 55 + клипы и RIFE-выход ~2 + запас). Иначе terminate.
- Цена диска: 100 GB x $0.10/GB-мес ≈ $0.014/ч, для теста пренебрежимо.
- Альтернатива для devops: параметр `volumeInGb` (pod volume на /workspace, не Network Volume) в `create-pod-novol`. Это правка `runpod.sh` и отдельное решение.

## 7. Время и стоимость (4090 $0.34/ч + диск $0.014/ч ≈ $0.355/ч)
| Фаза | Мин |
|---|---|
| Создание пода, SSH, тест скорости, `df`/`free` | 3-6 |
| torch 2.7.1 + ComfyUI (5-8 мин) **параллельно** с загрузкой весов A 37 GB (≤ 6.2 мин при 100 MB/s, обычно 2-4) | 6-9 |
| Запуск ComfyUI, первая загрузка моделей; веса B докачиваются в фоне | 2-3 |
| Пробный клип (49 кадров, 3 с) | 2-3 |
| Вариант A: 8 клипов (4 кадра x 2 seed) x 65 кадров | 12-16 |
| Вариант B (5B): 4 клипа | 12-16 |
| RIFE 16->32 fps для 12 клипов | 6-10 |
| Скачивание mp4 в репо, запас | 8-10 |
| **Итого** | **51-73** |

- Ожидаемо: ~1.0-1.2 ч x $0.355 = **$0.35-$0.45**.
- Пессимистично 100 мин: $0.60. **Жёсткий потолок плана: 120 мин или $1.00** (на 4090 120 мин = $0.71, на 3090 $0.46).
- Бюджет теста $2-3 перекрыт с большим запасом; ни одна фаза по отдельности его не превышает.

## 8. Порядок запуска (после одобрения)
1. Пользователь явно пишет «запускай» -> `RUNPOD_ALLOW_SPEND=yes` (после запуска сразу обратно `no`).
2. devops-agent: перед стартом read-only `runpod_video.sh gpus`. Затем `runpod_video.sh create-pod-novol wan-i2v COMMUNITY 100` (лимит $2/ч и цепочка 4090 -> 3090 -> A5000 уже внутри скрипта, `runpod.sh` для этого запуска не используется). Сообщает POD_ID, GPU, цену/ч, время. Цена > $0.50/ч (ожидаем ≤ $0.34) -> terminate и вопрос пользователю; цена > $2/ч -> terminate немедленно. Dead-man switch: `sleep 7200; runpodctl remove pod $RUNPOD_POD_ID`.
3. provisioner-agent, **лимит 15 мин** от SSH-ready до ComfyUI с моделями A:
   - сразу `speed_test.sh <URL high_noise fp8> 100`; провал = стоп и отчёт, devops терминирует и берёт другой хост;
   - `df -h /root` ≥ 75 GB, `free -g` (желательно ≥ 32 GB RAM, иначе смена экспертов идёт с диска и медленнее; < 16 GB = сменить хост);
   - `WS=/root/ws bash setup_comfyui.sh` (без доп. нод для A и B; RIFE-нода `ComfyUI-Frame-Interpolation` ставится скриптом) параллельно с `MODELS_DIR=/root/ws/ComfyUI/models download_models.sh models.manifest` под `setsid nohup`;
   - запуск ComfyUI на :8188 через `setsid nohup`, SSH-туннель на 127.0.0.1:8188;
   - после готовности A: в фоне `download_models.sh models_b.manifest`.
4. pipeline-agent: в `/object_info` есть `WanImageToVideo`, `Wan22ImageToVideoLatent`, `KSamplerAdvanced`, `LoraLoaderModelOnly`, `ModelSamplingSD3`, `CreateVideo`, `SaveVideo` и нода RIFE, модели видны в списках. Граф A (по шаблону ComfyUI «Wan2.2 14B I2V» с 4-step LoRA):
   `UNETLoader(high fp8) -> LoraLoaderModelOnly(1.0) -> ModelSamplingSD3(shift 5)` и то же для low;
   `LoadImage -> WanImageToVideo(704x480, length 65)`;
   `KSamplerAdvanced` high: steps 4, cfg 1, euler/simple, шаги 0-2, add_noise on, leftover noise on;
   `KSamplerAdvanced` low: шаги 2-4, add_noise off;
   `VAEDecode -> CreateVideo(16 fps) -> SaveVideo(mp4)`; ветка `RIFE x2 -> CreateVideo(32 fps) -> SaveVideo`.
   Граф B: шаблон «Wan2.2 5B ti2v» (`Wan22ImageToVideoLatent`, 20-30 шагов, cfg 5).
   Сначала пробник (49 кадров) и замер времени. Если пробник > 8 мин на 4090, стоп и пересмотр.
5. qa-agent: mp4 704x480, 65 кадров (A/B) и 129 кадров (32 fps), не чёрный и не шум, первый кадр совпадает с входной картинкой, число файлов верное (A: 8 + 8, B: 4 + 4).
6. mp4 скачаны в `workspace/output/wan_i2v_test/` ДО terminate.
7. `runpod.sh terminate <POD_ID>`, `pods` и `volumes` = `[]`, `RUNPOD_ALLOW_SPEND=no`.

## 9. Правила остановки
- Цена пода > $0.50/ч -> terminate и вопрос пользователю. Цена > $2/ч -> terminate немедленно.
- Скорость загрузки < 100 MB/s, свободного диска < 75 GB или RAM < 16 GB -> terminate, другой хост (не более 2 попыток, потом стоп).
- Провижининг > 15 мин -> стоп, отчёт оркестратору.
- OOM на A14B -> одна попытка с `--lowvram` / 49 кадров, затем только вариант B на том же поде.
- Общий жёсткий лимит **120 мин или $1.00** на тест, что раньше.

## 10. Риски
- **Сток**: 3090 и 4090 «Low», A5000 сейчас без стока. Создание может не пройти. Тогда либо ждать/повторить позже, либо B на 12-16 GB (3080 Ti $0.18/ч).
- **RAM хоста**: два эксперта fp8 по 14.3 GB. При < 32 GB RAM ComfyUI перечитывает их с диска при каждой смене (+20-40 с на клип), не фатально.
- **fp8 на 3090/A5000 (Ampere)**: аппаратных fp8-вычислений нет, веса хранятся в fp8, считаются в fp16; работает, но без ускорения. 4090 (Ada) fp8 поддерживает.
- **lightx2v 4-step** известен «замедленным» движением и слабее следует промпту, чем 20+ шагов без LoRA. Для теста приемлемо. Если движения мало: схема 3 сэмплеров (2 шага high без LoRA с cfg 3.5) или LoRA strength high-noise 0.5-0.8.
- **Промпты**: готовые `workspace/prompts/built/*.txt` — Danbooru-теги для SDXL. Wan нужен короткий естественный английский текст про **движение и камеру**. prompt-engineer-agent пока не запускался; без него на пробный клип пойдёт временный промпт, итоговые клипы лучше не гонять до готовых промптов.
- **5B на 480p** ниже своего обучающего разрешения (1280x704), качество может просесть. Для этого и делаем A/B.
- Оценки времени не замерены на нашем хосте. Пробник уточнит их до основной партии.

## 11. Открытые вопросы к пользователю
Нет блокирующих. Перед «запускай» проверить: (1) промпты `wan_i2v_s01-s04` (готовы, пользователь смотрит; кадр 3.4 рискованный, на нём стоит сделать несколько seed), (2) `runpod_video.sh` готов (создан devops-agent'ом, проверен без расходов, `create-*` не тестировался), (3) повторная проверка стока и цен 4090/3090.
