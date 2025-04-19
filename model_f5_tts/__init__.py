class TTSLabModel:
    models = [
        {
            "key": "F5-TTS_v1",
            "id": "f5-tts-v1",
            "name": "F5 TTS v1",
            "description": "F5-TTSv1 model.",
            "voice_cloning": True,
            "additional_args": [
                {
                    "id": "ref_text",
                    "name": "Reference Text",
                    "description": "This is optional, feel free to leave blank to auto-transcribe",
                    "type": "text",
                    "default": "",
                    "required": False
                }
            ],
        },
        {
            "key": "E2-TTS",
            "id": "E2-TTS",
            "name": "E2 TTS",
            "description": "E2-TTS model",
            "voice_cloning": True,
            "additional_args": [
                {
                    "id": "ref_text",
                    "name": "Reference Text",
                    "description": "This is optional, feel free to leave blank to auto-transcribe",
                    "type": "text",
                    "default": "",
                    "required": False
                }
            ],
        },
    ]

    def __init__(self):
        from f5_tts.api import F5TTS

        self.F5TTS = F5TTS

    def __call__(
        self,
        model_id,
        text,
        reference_audio,
        speaker_id,
        output_file=None,
        additional_args=None,
    ):
        if speaker_id:
            raise NotImplementedError("Voice cloning is not yet supported.")
        
        # Ensure additional_args is a dict for unpacking
        additional_args = additional_args or {}

        if model_id == "f5-tts-v1" or model_id == "F5-TTS_v1":
            return self._run_f5_tts_v1(text, reference_audio, output_file=output_file, **additional_args)
        elif model_id == "E2-TTS":
            return self._run_e2_tts(text, reference_audio, output_file=output_file, **additional_args)
        else:
            raise ValueError(f"Model {model_id} not found.")

    def _run_f5_tts_v1(self, text, reference_audio, output_file=None, progress=None, ref_text="", **kwargs):
        model = self.F5TTS("F5TTS_v1_Base")
        model.infer(
            ref_file=reference_audio,
            ref_text=ref_text,
            gen_text=text,
            progress=progress,
            file_wave=output_file,
            **kwargs
        )

    def _run_e2_tts(self, text, reference_audio, output_file=None, progress=None, ref_text="", **kwargs):
        model = self.F5TTS("E2TTS_Base")
        model.infer(
            ref_file=reference_audio,
            ref_text=ref_text,
            gen_text=text,
            progress=progress,
            file_wave=output_file,
            **kwargs
        )

if __name__ == "__main__":
    model = TTSLabModel()
    import os
    model("F5-TTS_v1", "Hello, world!", os.path.expanduser("~/ref_f5.wav"), None, "output.wav")
