from __future__ import annotations
from typing import Tuple, Hashable, Sequence, Dict, Optional, List, TYPE_CHECKING
from typing_extensions import Self
from abc import ABC, abstractmethod
from datetime import datetime

import xarray as xr

if TYPE_CHECKING:
    from datatree import DataTree

from .eof import EOF
from ..preprocessing.preprocessor import Preprocessor
from ..data_container import DataContainer
from ..utils.data_types import DataObject, DataArray, DataSet
from ..utils.xarray_utils import convert_to_dim_type
from ..utils.sanity_checks import validate_input_type
from .._version import __version__


class _BaseCrossModel(ABC):
    """
    Abstract base class for cross-decomposition models.

    Parameters:
    -------------
    n_modes: int, default=10
        Number of modes to calculate.
    center: bool, default=True
        Whether to center the input data.
    standardize: bool, default=False
        Whether to standardize the input data.
    use_coslat: bool, default=False
        Whether to use cosine of latitude for scaling.
    n_pca_modes: int, default=None
        Number of PCA modes to calculate.
    compute : bool, default=True
        Whether to compute the decomposition immediately.
    sample_name: str, default="sample"
        Name of the new sample dimension.
    feature_name: str, default="feature"
        Name of the new feature dimension.
    solver: {"auto", "full", "randomized"}, default="auto"
        Solver to use for the SVD computation.
    solver_kwargs: dict, default={}
        Additional keyword arguments to pass to the solver.

    """

    def __init__(
        self,
        n_modes=10,
        center=True,
        standardize=False,
        use_coslat=False,
        n_pca_modes=None,
        compute=True,
        sample_name="sample",
        feature_name="feature",
        solver="auto",
        random_state=None,
        solver_kwargs={},
    ):
        self.n_modes = n_modes
        self.sample_name = sample_name
        self.feature_name = feature_name

        # Define model parameters
        self._params = {
            "n_modes": n_modes,
            "center": center,
            "standardize": standardize,
            "use_coslat": use_coslat,
            "n_pca_modes": n_pca_modes,
            "compute": compute,
            "sample_name": sample_name,
            "feature_name": feature_name,
            "solver": solver,
            "random_state": random_state,
        }

        self._solver_kwargs = solver_kwargs
        self._solver_kwargs.update(
            {"solver": solver, "random_state": random_state, "compute": compute}
        )
        self._preprocessor_kwargs = {
            "sample_name": sample_name,
            "feature_name": feature_name,
            "with_center": center,
            "with_std": standardize,
            "with_coslat": use_coslat,
        }

        # Define analysis-relevant meta data
        self.attrs = {"model": "BaseCrossModel"}
        self.attrs.update(
            {
                "software": "xeofs",
                "version": __version__,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        self.attrs.update(self._params)

        # Initialize preprocessors to scale and stack left (1) and right (2) data
        self.preprocessor1 = Preprocessor(**self._preprocessor_kwargs)
        self.preprocessor2 = Preprocessor(**self._preprocessor_kwargs)

        # Initialize the data container that stores the results
        self.data = DataContainer()

        # Initialize PCA objects
        self.pca1 = (
            EOF(n_modes=n_pca_modes, compute=self._params["compute"])
            if n_pca_modes
            else None
        )
        self.pca2 = (
            EOF(n_modes=n_pca_modes, compute=self._params["compute"])
            if n_pca_modes
            else None
        )

    def fit(
        self,
        data1: DataObject,
        data2: DataObject,
        dim: Hashable | Sequence[Hashable],
        weights1: Optional[DataObject] = None,
        weights2: Optional[DataObject] = None,
    ) -> Self:
        """
        Fit the model to the data.

        Parameters
        ----------
        data1: DataArray | Dataset | List[DataArray]
            Left input data.
        data2: DataArray | Dataset | List[DataArray]
            Right input data.
        dim: Hashable | Sequence[Hashable]
            Define the sample dimensions. The remaining dimensions
            will be treated as feature dimensions.
        weights1: Optional[DataObject]
            Weights to be applied to the left input data.
        weights2: Optional[DataObject]
            Weights to be applied to the right input data.

        """
        validate_input_type(data1)
        validate_input_type(data2)
        if weights1 is not None:
            validate_input_type(weights1)
        if weights2 is not None:
            validate_input_type(weights2)

        self.sample_dims = convert_to_dim_type(dim)
        # Preprocess data1
        data1 = self.preprocessor1.fit_transform(data1, self.sample_dims, weights1)
        # Preprocess data2
        data2 = self.preprocessor2.fit_transform(data2, self.sample_dims, weights2)

        return self._fit_algorithm(data1, data2)

    def transform(
        self, data1: Optional[DataObject] = None, data2: Optional[DataObject] = None
    ) -> Sequence[DataArray]:
        """
        Abstract method to transform the data.


        """
        if data1 is None and data2 is None:
            raise ValueError("Either data1 or data2 must be provided.")

        if data1 is not None:
            validate_input_type(data1)
            # Preprocess data1
            data1 = self.preprocessor1.transform(data1)
        if data2 is not None:
            validate_input_type(data2)
            # Preprocess data2
            data2 = self.preprocessor2.transform(data2)

        return self._transform_algorithm(data1, data2)

    @abstractmethod
    def _fit_algorithm(self, data1: DataArray, data2: DataArray) -> Self:
        """
        Fit the model to the preprocessed data. This method needs to be implemented in the respective
        subclass.

        Parameters
        ----------
        data1, data2: DataArray
            Preprocessed input data of two dimensions: (`sample_name`, `feature_name`)

        """
        raise NotImplementedError

    @abstractmethod
    def _transform_algorithm(
        self, data1: Optional[DataArray] = None, data2: Optional[DataArray] = None
    ) -> Sequence[DataArray]:
        """
        Transform the preprocessed data. This method needs to be implemented in the respective
        subclass.

        Parameters
        ----------
        data1, data2: DataArray
            Preprocessed input data of two dimensions: (`sample_name`, `feature_name`)

        """
        raise NotImplementedError

    @abstractmethod
    def inverse_transform(self, mode) -> Tuple[DataObject, DataObject]:
        raise NotImplementedError

    def components(self) -> Tuple[DataObject, DataObject]:
        """Get the components."""
        comps1 = self.data["components1"]
        comps2 = self.data["components2"]

        components1: DataObject = self.preprocessor1.inverse_transform_components(
            comps1
        )
        components2: DataObject = self.preprocessor2.inverse_transform_components(
            comps2
        )
        return components1, components2

    def scores(self) -> Tuple[DataArray, DataArray]:
        """Get the scores."""
        scores1 = self.data["scores1"]
        scores2 = self.data["scores2"]

        scores1: DataArray = self.preprocessor1.inverse_transform_scores(scores1)
        scores2: DataArray = self.preprocessor2.inverse_transform_scores(scores2)
        return scores1, scores2

    def compute(self, verbose: bool = False):
        """Compute and load delayed model results.

        Parameters
        ----------
        verbose : bool
            Whether or not to provide additional information about the computing progress.

        """
        self.data.compute(verbose=verbose)

    def get_params(self) -> Dict:
        """Get the model parameters."""
        return self._params

    def serialize(self, save_data: bool = False) -> DataSet:
        """Serialize a complete model with its preprocessors."""
        from datatree import DataTree

        data = {}
        for key, x in self.data.items():
            if self.data._allow_compute[key] or save_data:
                data[key] = x.assign_attrs(
                    {"allow_compute": self.data._allow_compute[key]}
                )
            else:
                # create an empty placeholder array
                data[key] = xr.DataArray().assign_attrs(
                    {"allow_compute": False, "placeholder": True}
                )

        # Store the DataContainer items as data_vars, and the model parameters as global attrs
        ds_model = xr.Dataset(data, attrs=dict(params=self.get_params()))
        # Set as the root node of the tree
        dt = DataTree(name="model", data=ds_model)

        # Retrieve the tree representation of the preprocessor
        dt["preprocessor1"] = self.preprocessor1.serialize_all()
        dt["preprocessor2"] = self.preprocessor2.serialize_all()
        dt.preprocessor1.parent = dt
        dt.preprocessor2.parent = dt

        return dt

    def save(
        self,
        path: str,
        save_data: bool = False,
        **kwargs,
    ):
        """Save the model to zarr.

        Parameters
        ----------
        path : str
            Path to save the model zarr store.
        save_data : str
            Whether or not to save the full input data along with the fitted components.
        **kwargs
            Additional keyword arguments to pass to `DataTree.to_zarr()`.

        """
        dt = self.serialize(save_data=save_data)

        # Handle rotator models by separately serializing the original model
        # and attaching as a child of the rotator model
        if hasattr(self, "model"):
            dt["model"] = self.model.serialize()

        dt.to_zarr(path, **kwargs)

    @classmethod
    def deserialize(cls, dt: DataTree) -> Self:
        """Deserialize the model and its preprocessors from a DataTree."""
        # Recreate the model with parameters set by root level attrs
        model = cls(**dt.attrs["params"])

        # Recreate the Preprocessors from their trees
        model.preprocessor1 = Preprocessor.deserialize_all(dt.preprocessor1)
        model.preprocessor2 = Preprocessor.deserialize_all(dt.preprocessor2)

        # Create the model's DataContainer from the root level data_vars
        model.data = DataContainer({k: dt[k] for k in dt.data_vars})

        return model

    @classmethod
    def load(cls, path: str, **kwargs) -> Self:
        """Load a saved model from zarr.

        Parameters
        ----------
        path : str
            Path to the saved model zarr store.
        **kwargs
            Additional keyword arguments to pass to `open_datatree()`.

        Returns
        -------
        model : _BaseCrossModel
            The loaded model.

        """
        from datatree import open_datatree

        dt = open_datatree(path, engine="zarr", **kwargs)

        model = cls.deserialize(dt)

        # Rebuild any attached model
        if dt.get("model") is not None:
            # Recreate the original model from its tree, assuming we should
            # use the first base class of the current model
            model.model = cls.__bases__[0].deserialize(dt.model)

        for key in model.data.keys():
            model.data._allow_compute[key] = model.data[key].attrs["allow_compute"]
            model._validate_loaded_data(model.data[key])

        return model

    def _validate_loaded_data(self, data: DataArray):
        """Optionally check the loaded data for placeholders."""
        pass
