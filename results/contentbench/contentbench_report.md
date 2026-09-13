# ContentBench comparison results

Positive effects favor Rime. Confidence intervals use the family-clustered bootstrap. Holm p-values cover the planned competitor comparisons included in this run.

| competitor | items | families | Kish G | judgments | Rime - competitor [95% CI] | W/T/L count | W/T/L proportion | raw p | Holm p | claim status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| cartesia_sonic3_default | 400 | 223 | 80.73 | 2240 | +0.201 [+0.118, +0.280] | 232/41/127 | 58.0%/10.2%/31.8% | 5e-06 | 2e-05 | rime_direction_supported |
| deepgram_aura2_thalia | 400 | 223 | 80.73 | 2240 | -0.153 [-0.229, -0.076] | 149/32/219 | 37.2%/8.0%/54.8% | 1e-05 | 2e-05 | competitor_direction_supported |
| elevenlabs_flash25_cindycasualnarrator | 400 | 223 | 80.73 | 2240 | -0.164 [-0.257, -0.071] | 147/30/223 | 36.8%/7.5%/55.8% | 0.000215 | 0.000215 | competitor_direction_supported |
| openai_4ominitts_coral | 400 | 223 | 80.73 | 2240 | +0.310 [+0.215, +0.414] | 243/28/129 | 60.8%/7.0%/32.2% | 5e-06 | 2e-05 | rime_direction_supported |

## Coarser dependence sensitivity

This ContentBench sensitivity clusters literature excerpts by author and other items by genre. It can qualify a primary claim but cannot license one.

| competitor | clusters | Kish G | Rime - competitor [95% CI] | raw p | Holm p |
|---|---:|---:|---:|---:|---:|
| cartesia_sonic3_default | 24 | 3.83 | +0.201 [+0.123, +0.350] | 4e-05 | 0.00016 |
| deepgram_aura2_thalia | 24 | 3.83 | -0.153 [-0.271, -0.071] | 0.000465 | 0.001395 |
| elevenlabs_flash25_cindycasualnarrator | 24 | 3.83 | -0.164 [-0.323, -0.060] | 0.003725 | 0.00745 |
| openai_4ominitts_coral | 24 | 3.83 | +0.310 [+0.006, +0.441] | 0.01932 | 0.01932 |
