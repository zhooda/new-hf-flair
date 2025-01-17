from typing import List

import torch

import flair.embeddings
import flair.nn
from flair.data import Sentence, TextPair


class TextPairClassifier(flair.nn.DefaultClassifier[TextPair, TextPair]):
    """
    Text Pair Classification Model for tasks such as Recognizing Textual Entailment, build upon TextClassifier.
    The model takes document embeddings and puts resulting text representation(s) into a linear layer to get the
    actual class label. We provide two ways to embed the DataPairs: Either by embedding both DataPoints
    and concatenating the resulting vectors ("embed_separately=True") or by concatenating the DataPoints and embedding
    the resulting vector ("embed_separately=False").
    """

    def __init__(
        self,
        embeddings: flair.embeddings.DocumentEmbeddings,
        label_type: str,
        embed_separately: bool = False,
        **classifierargs,
    ):
        """
        Initializes a TextClassifier
        :param embeddings: embeddings used to embed each data point
        :param label_dictionary: dictionary of labels you want to predict
        :param multi_label: auto-detected by default, but you can set this to True to force multi-label prediction
        or False to force single-label prediction
        :param multi_label_threshold: If multi-label you can set the threshold to make predictions
        :param loss_weights: Dictionary of weights for labels for the loss function
        (if any label's weight is unspecified it will default to 1.0)
        """
        super().__init__(
            **classifierargs,
            embeddings=embeddings,
            final_embedding_size=2 * embeddings.embedding_length if embed_separately else embeddings.embedding_length,
        )

        self._label_type = label_type

        self.embed_separately = embed_separately

        if not self.embed_separately:
            # set separator to concatenate two sentences
            self.sep = " "
            if isinstance(
                self.document_embeddings,
                flair.embeddings.document.TransformerDocumentEmbeddings,
            ):
                if self.document_embeddings.tokenizer.sep_token:
                    self.sep = " " + str(self.document_embeddings.tokenizer.sep_token) + " "
                else:
                    self.sep = " [SEP] "

        # auto-spawn on GPU if available
        self.to(flair.device)

    @property
    def label_type(self):
        return self._label_type

    def _get_data_points_from_sentence(self, sentence: TextPair) -> List[TextPair]:
        return [sentence]

    def _get_embedding_for_data_point(self, prediction_data_point: TextPair) -> torch.Tensor:
        embedding_names = self.embeddings.get_names()
        if self.embed_separately:
            self.embeddings.embed([prediction_data_point.first, prediction_data_point.second])
            return torch.cat(
                [
                    prediction_data_point.first.get_embedding(embedding_names),
                    prediction_data_point.second.get_embedding(embedding_names),
                ],
                0,
            )
        else:
            concatenated_sentence = Sentence(
                prediction_data_point.first.to_tokenized_string()
                + self.sep
                + prediction_data_point.second.to_tokenized_string(),
                use_tokenizer=False,
            )
            self.embeddings.embed(concatenated_sentence)
            return concatenated_sentence.get_embedding(embedding_names)

    def _get_state_dict(self):
        model_state = {
            **super()._get_state_dict(),
            "document_embeddings": self.embeddings.save_embeddings(use_state_dict=False),
            "label_dictionary": self.label_dictionary,
            "label_type": self.label_type,
            "multi_label": self.multi_label,
            "multi_label_threshold": self.multi_label_threshold,
            "weight_dict": self.weight_dict,
            "embed_separately": self.embed_separately,
        }
        return model_state

    @classmethod
    def _init_model_with_state_dict(cls, state, **kwargs):
        return super()._init_model_with_state_dict(
            state,
            embeddings=state.get("document_embeddings"),
            label_dictionary=state.get("label_dictionary"),
            label_type=state.get("label_type"),
            multi_label=state.get("multi_label_threshold", 0.5),
            loss_weights=state.get("weight_dict"),
            embed_separately=state.get("embed_separately"),
            **kwargs,
        )
