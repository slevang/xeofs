from abc import ABC, abstractmethod

import numpy as np
import xarray as xr
import scipy as sc


from ..preprocessing.scaler import Scaler, ListScaler
from ..preprocessing.stacker import DataArrayStacker, DataArrayListStacker, DatasetStacker
from ..utils.data_types import DataArray, DataArrayList, Dataset, XarrayData
from ..utils.xarray_utils import get_dims

class _BaseModel(ABC):
    '''
    Abstract base class for EOF model. 

    Parameters:
    -------------
    n_modes: int, default=10
        Number of modes to calculate.
    standardize: bool, default=False
        Whether to standardize the input data.
    use_coslat: bool, default=False
        Whether to use cosine of latitude for scaling.
    use_weights: bool, default=False
        Whether to use weights.

    '''
    def __init__(self, n_modes=10, standardize=False, use_coslat=False, use_weights=False, **kwargs):
        self._params = {
            'n_modes': n_modes,
            'standardize': standardize,
            'use_coslat': use_coslat,
            'use_weights': use_weights
        }
        self._scaling_params = {
            'with_std': standardize,
            'with_coslat': use_coslat,
            'with_weights': use_weights
        }
    
    @staticmethod
    def _create_scaler(data: XarrayData | DataArrayList, **kwargs):
        if isinstance(data, (xr.DataArray, xr.Dataset)):
            return Scaler(**kwargs)
        elif isinstance(data, list):
            return ListScaler(**kwargs)
        else:
            raise ValueError(f'Cannot scale data of type: {type(data)}')
    
    @staticmethod
    def _create_stacker(data: XarrayData | DataArrayList, **kwargs):
        if isinstance(data, xr.DataArray):
            return DataArrayStacker(**kwargs)
        elif isinstance(data, list):
            return DataArrayListStacker(**kwargs)
        elif isinstance(data, xr.Dataset):
            return DatasetStacker(**kwargs)
        else:
            raise ValueError(f'Cannot stack data of type: {type(data)}')

    def _preprocessing(self, data, dims, weights=None):
        '''Preprocess the data.
        
        This will scale and stack the data.
        
        Parameters:
        -------------
        data: xr.DataArray or list of xarray.DataArray
            Input data.
        dims: tuple
            Tuple specifying the sample dimensions. The remaining dimensions
            will be treated as feature dimensions.
        weights: xr.DataArray or xr.Dataset or None, default=None
            If specified, the input data will be weighted by this array.
        
        '''
        # Set sample and feature dimensions
        sample_dims, feature_dims = get_dims(data, sample_dims=dims)
        self.dims = {'sample': sample_dims, 'feature': feature_dims}
        
        # Scale the data
        self.scaler = self._create_scaler(data, **self._scaling_params)
        self.scaler.fit(data, sample_dims, feature_dims, weights)  # type: ignore
        data = self.scaler.transform(data)

        # Stack the data
        self.stacker = self._create_stacker(data)
        self.stacker.fit(data, sample_dims, feature_dims)  # type: ignore
        self.data = self.stacker.transform(data)  # type: ignore

    @abstractmethod
    def fit(self, data, dims, weights=None):
        '''
        Abstract method to fit the model.

        Parameters:
        -------------
        data: xr.DataArray or list of xarray.DataArray
            Input data.
        dims: tuple
            Tuple specifying the sample dimensions. The remaining dimensions 
            will be treated as feature dimensions.
        weights: xr.DataArray or xr.Dataset or None, default=None
            If specified, the input data will be weighted by this array.

        '''
        # Here follows the implementation to fit the model
        # Typically you want to start by calling self._preprocessing(data, dims, weights)
        # ATTRIBUTES TO BE DEFINED:
        self._total_variance = None
        self._singular_values = None
        self._explained_variance = None
        self._explained_variance_ratio = None
        self._components = None
        self._scores = None

    @abstractmethod
    def transform(self):
        raise NotImplementedError

    @abstractmethod
    def inverse_transform(self):
        raise NotImplementedError

    def singular_values(self):
        '''Return the singular values of the model.

        Returns:
        ----------
        singular_values: DataArray
            Singular values of the fitted model.

        '''
        return self._singular_values
    
    def explained_variance(self):
        '''Return explained variance.'''
        return self._explained_variance
    
    def explained_variance_ratio(self):
        '''Return explained variance ratio.'''
        return self._explained_variance_ratio

    def components(self):
        '''Return the components.
        
        The components in EOF anaylsis are the eigenvectors of the covariance matrix
        (or correlation) matrix. Other names include the principal components or EOFs.

        Returns:
        ----------
        components: DataArray | Dataset | List[DataArray]
            Components of the fitted model.

        '''
        return self.stacker.inverse_transform_components(self._components)  #type: ignore
    
    def scores(self):
        '''Return the scores.
        
        The scores in EOF anaylsis are the projection of the data matrix onto the 
        eigenvectors of the covariance matrix (or correlation) matrix. 
        Other names include the principal component (PC) scores or just PCs.

        Returns:
        ----------
        components: DataArray | Dataset | List[DataArray]
            Scores of the fitted model.

        '''
        return self.stacker.inverse_transform_scores(self._scores)  #type: ignore

    def get_params(self):
        return self._params

    def compute(self):
        '''Computing the model will load and compute Dask arrays.'''

        self._total_variance = self._total_variance.compute()  # type: ignore
        self._singular_values = self._singular_values.compute()   # type: ignore
        self._explained_variance = self._explained_variance.compute()   # type: ignore
        self._explained_variance_ratio = self._explained_variance_ratio.compute()   # type: ignore
        self._components = self._components.compute()    # type: ignore
        self._scores = self._scores.compute()    # type: ignore