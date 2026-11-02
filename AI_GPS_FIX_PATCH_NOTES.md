# AI image analysis and device location fixes

This change set is being prepared from the supplied project ZIP. Targeted fixes:

- Run the shipped MobileNetV2 civic classifier against the actual incoming image upload, before Supabase Storage consumes the stream.
- Remove random, filename-based, and colour-only fallback guesses. Show an explicit unavailable / manual-entry state instead.
- Let citizens accept the AI category suggestion or manually select the correct category.
- Improve browser geolocation with high accuracy, fresh coordinates, a longer timeout, explicit secure-context/permission errors, accuracy feedback, retry, and manual landmark fallback.
- Validate finite coordinate values and reject invalid 0,0 coordinates.

Local smoke tests run against bundled sample photos classified all four categories correctly. Full browser-to-Supabase integration and production deployment remain to be verified after deployment.
