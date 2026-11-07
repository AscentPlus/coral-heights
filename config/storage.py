from whitenoise.storage import CompressedManifestStaticFilesStorage


class SafeCompressedManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """
    WhiteNoise storage that extends CompressedManifestStaticFilesStorage
    to gracefully fall back to unhashed file names instead of raising a
    500 ValueError if a static file reference is missing from the manifest.
    """
    manifest_strict = False

    def stored_name(self, name):
        try:
            return super().stored_name(name)
        except ValueError:
            return name

