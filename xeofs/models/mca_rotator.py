import numpy as np
import xarray as xr
from dask.diagnostics.progress import ProgressBar
from typing import List

from ._base_rotator import _BaseRotator
from .mca import MCA, ComplexMCA
from ..utils.rotation import promax
from ..utils.data_types import XarrayData, DataArrayList, Dataset, DataArray


class MCARotator(_BaseRotator):
    '''Rotates a solution obtained from ``xe.models.MCA``.
    
    Parameters
    ----------
    n_rot : int
        Number of modes to be rotated.
    power : int
        Defines the power of Promax rotation. Choosing ``power=1`` equals
        a Varimax solution (the default is 1).
    max_iter : int
        Number of maximal iterations for obtaining the rotation matrix
        (the default is 1000).
    rtol : float
        Relative tolerance to be achieved for early stopping the iteration
        process (the default is 1e-8).
    squared_loadings : bool, default=False
        Determines the method of constructing the combined vectors of loadings. If set to True, the combined 
        vectors are loaded with the singular values ("squared loadings"), conserving the squared covariance 
        under rotation. This allows for estimation of mode importance after rotation. If set to False, 
        follows the Cheng & Dunkerton method [1]_ of loading with the square root of singular values.
    
    References
    ----------
    .. [1] Cheng, X., Dunkerton, T.J., 1995. Orthogonal Rotation of Spatial Patterns Derived from Singular Value Decomposition Analysis. J. Climate 8, 2631–2643. https://doi.org/10.1175/1520-0442(1995)008<2631:OROSPD>2.0.CO;2

    '''

    def __init__(self, n_rot: int, power: int = 1, max_iter: int = 1000, rtol: float = 1e-8, squared_loadings: bool = False):
        super().__init__(n_rot=n_rot, power=power, max_iter=max_iter, rtol=rtol)
        self._params['squared_loadings'] = squared_loadings

    def fit(self, model: MCA | ComplexMCA):
        '''Fit the model.
        
        Parameters
        ----------
        model : xe.models.MCA
            A MCA model solution.
            
        '''
        self._model = model
        
        n_rot = self._params.get('n_rot')
        power = self._params.get('power')
        max_iter = self._params.get('max_iter')
        rtol = self._params.get('rtol')
        use_squared_loadings = self._params.get('squared_loadings')


        # Construct the combined vector of loadings
        # NOTE: In the methodology used by Cheng & Dunkerton (CD), the combined vectors are "loaded" or weighted 
        # with the square root of the singular values, akin to what is done in standard Varimax rotation. This method 
        # ensures that the total amount of covariance is conserved during the rotation process.
        # However, in Maximum Covariance Analysis (MCA), the focus is usually on the squared covariance to determine
        # the importance of a given mode. The approach adopted by CD does not preserve the squared covariance under
        # rotation, making it impossible to estimate the importance of modes post-rotation.
        # To resolve this issue, one possible workaround is to rotate the singular vectors that have been "loaded"
        # or weighted with the singular values ("squared loadings"), as opposed to the square root of the singular values.
        # In doing so, the squared covariance remains conserved under rotation, allowing for the estimation of the 
        # modes' importance. 
        if use_squared_loadings:
            # Squared loadings approach conserving squared covariance
            scaling = self._model._singular_values.sel(mode=slice(1, n_rot))
        else:
            # Cheng & Dunkerton approach conserving covariance
            scaling = np.sqrt(self._model._singular_values.sel(mode=slice(1, n_rot)))

        svecs1 = self._model._singular_vectors1.sel(mode=slice(1, n_rot))
        svecs2 = self._model._singular_vectors2.sel(mode=slice(1, n_rot))
        loadings = xr.concat([svecs1, svecs2], dim='feature') * scaling

        # Rotate loadings
        rot_loadings, rot_matrix, Phi =  xr.apply_ufunc(
            promax,
            loadings,
            power,
            input_core_dims=[['feature', 'mode'], []],
            output_core_dims=[['feature', 'mode'], ['mode', 'mode1'], ['mode', 'mode1']],
            kwargs={'max_iter': max_iter, 'rtol': rtol},
            dask='allowed'
        )
        self._rotation_matrix = rot_matrix

        # Rotated (loaded) singular vectors
        svecs1_rot = rot_loadings.isel(feature=slice(0, svecs1.coords['feature'].size))
        svecs2_rot = rot_loadings.isel(feature=slice(svecs1.coords['feature'].size, None))

        # Normalization factor of singular vectors
        norm1 = xr.apply_ufunc(np.linalg.norm, svecs1_rot, input_core_dims=[['feature']], output_core_dims=[[]], kwargs={'axis': -1}, dask='allowed')
        norm2 = xr.apply_ufunc(np.linalg.norm, svecs2_rot, input_core_dims=[['feature']], output_core_dims=[[]], kwargs={'axis': -1}, dask='allowed')

        # Rotated (normalized) singular vectors
        svecs1_rot = svecs1_rot / norm1
        svecs2_rot = svecs2_rot / norm2

        # Remove the squaring introduced by the squared loadings approach
        if use_squared_loadings:
            norm1 = norm1 ** 0.5
            norm2 = norm2 ** 0.5
        
        # Explained variance (= "singular values")
        expvar = norm1 * norm2

        # Reorder according to variance
        # NOTE: For delayed objects, the index must be computed. .values will rensure that the index is computed
        # NOTE: The index must be computed before sorting since argsort is not (yet) implemented in dask
        idx_sort = expvar.values.argsort()[::-1]
        self._idx_expvar = idx_sort
        
        self._explained_variance = expvar.isel(mode=idx_sort).assign_coords(mode=expvar.mode)
        self._squared_covariance_fraction = self._explained_variance ** 2 / self._model._squared_total_variance

        self._norm1 = norm1.isel(mode=idx_sort).assign_coords(mode=norm1.mode)
        self._norm2 = norm2.isel(mode=idx_sort).assign_coords(mode=norm2.mode)
        
        self._singular_vectors1 = svecs1_rot.isel(mode=idx_sort).assign_coords(mode=svecs1_rot.mode)
        self._singular_vectors2 = svecs2_rot.isel(mode=idx_sort).assign_coords(mode=svecs2_rot.mode)

        # Rotate scores using rotation matrix
        scores1 = self._model._scores1.sel(mode=slice(1,n_rot))
        scores2 = self._model._scores2.sel(mode=slice(1,n_rot))
        R = self._get_rotation_matrix(inverse_transpose=True)
        scores1 = xr.dot(scores1, R, dims='mode1')
        scores2 = xr.dot(scores2, R, dims='mode1')

        # Reorder scores according to variance
        scores1 = scores1.isel(mode=idx_sort).assign_coords(mode=scores1.mode)
        scores2 = scores2.isel(mode=idx_sort).assign_coords(mode=scores2.mode)
        
        self._scores1 = scores1
        self._scores2 = scores2

        # Ensure consitent signs for deterministic output
        idx_max_value = abs(rot_loadings).argmax('feature').compute()
        flip_signs = xr.apply_ufunc(np.sign, rot_loadings.isel(feature=idx_max_value), dask='allowed')
        # Drop all dimensions except 'mode' so that the index is clean
        for dim, coords in flip_signs.coords.items():
            if dim != 'mode':
                flip_signs = flip_signs.drop(dim)
        self._singular_vectors1 *= flip_signs
        self._singular_vectors2 *= flip_signs
        self._scores1 *= flip_signs
        self._scores2 *= flip_signs

        self._mode_signs = flip_signs



    def transform(self, **kwargs) -> XarrayData | DataArrayList:
        '''Project new "unseen" data onto the rotated singular vectors.

        Parameters
        ----------
        data1 : xr.DataArray | xr.Dataset | xr.DataArraylist
            Data to be projected onto the rotated singular vectors of the first dataset.
        data2 : xr.DataArray | xr.Dataset | xr.DataArraylist
            Data to be projected onto the rotated singular vectors of the second dataset.

        Returns
        -------
        xr.DataArray | xr.Dataset | xr.DataArraylist
            Projected data.
        
        '''
        # raise error if no data is provided
        if not kwargs:
            raise ValueError('No data provided. Please provide data1 and/or data2.')
    
        n_rot = self._params['n_rot']
        expvar = self._explained_variance.sel(mode=slice(1, self._params['n_rot']))
        rot_matrix = self._get_rotation_matrix(inverse_transpose=True)

        results = []

        if 'data1' in kwargs:

            data1 = kwargs['data1']
            # Select the (non-rotated) singular vectors of the first dataset
            svecs1 = self._model._singular_vectors1.sel(mode=slice(1, n_rot))
            
            # Preprocess the data
            data1 = self._model.scaler1.transform(data1)  #type: ignore
            data1 = self._model.stacker1.transform(data1)  #type: ignore
            
            # Compute non-rotated scores by project the data onto non-rotated components
            projections1 = xr.dot(data1, svecs1) / expvar**0.5
            # Rotate the scores
            projections1 = xr.dot(projections1, rot_matrix, dims='mode1')
            # Reorder according to variance
            projections1 = projections1.isel(mode=self._idx_expvar).assign_coords(mode=projections1.mode)
            # Determine the sign of the scores
            projections1 *= self._mode_signs

            # Unstack the projections
            projections1 = self._model.stacker1.inverse_transform_scores(projections1)

            results.append(projections1)


        if 'data2' in kwargs:

            data2 = kwargs['data2']            
            # Select the (non-rotated) singular vectors of the second dataset
            svecs2 = self._model._singular_vectors2.sel(mode=slice(1, n_rot))
            
            # Preprocess the data
            data2 = self._model.scaler2.transform(data2)  #type: ignore
            data2 = self._model.stacker2.transform(data2)  #type: ignore
            
            # Compute non-rotated scores by project the data onto non-rotated components
            projections2 = xr.dot(data2, svecs2) / expvar**0.5
            # Rotate the scores
            projections2 = xr.dot(projections2, rot_matrix, dims='mode1')
            # Reorder according to variance
            projections2 = projections2.isel(mode=self._idx_expvar).assign_coords(mode=projections2.mode)
            # Determine the sign of the scores
            projections2 *= self._mode_signs


            # Unstack the projections
            projections2 = self._model.stacker2.inverse_transform_scores(projections2)

            results.append(projections2)
        
        if len(results) == 1:
            return results[0]
        else:
            return results

    def inverse_transform(self, mode: int | List[int] | slice = slice(None)):
        '''Reconstruct the original data from the rotated singular vectors.
        
        Parameters
        ----------
        mode : int | list[int] | slice
            Modes to be used for reconstruction.
            
        Returns
        -------
        xr.DataArray | xr.Dataset | xr.DataArraylist
            Reconstructed data.
            
        '''
        # Singular vectors
        svecs1 = self._singular_vectors1.sel(mode=mode)
        svecs2 = self._singular_vectors2.sel(mode=mode)

        # Scores = projections
        scores1 = self._scores1.sel(mode=mode)
        scores2 = self._scores2.sel(mode=mode)

        # Reconstruct the data
        data1 = xr.dot(scores1, svecs1.conj(), dims='mode')
        data2 = xr.dot(scores2, svecs2.conj(), dims='mode')

        # Unstack the data
        data1 = self._model.stacker1.inverse_transform_data(data1)
        data2 = self._model.stacker2.inverse_transform_data(data2)

        # Rescale the data
        data1 = self._model.scaler1.inverse_transform(data1)  # type: ignore
        data2 = self._model.scaler2.inverse_transform(data2)  # type: ignore

        return data1, data2
    
    def compute(self, verbose: bool = False):
        '''Compute the rotated solution.
        
        Parameters
        ----------
        verbose : bool
            If True, print information about the computation process.
            
        '''
        
        self._model.compute(verbose=verbose)
        if verbose:
            with ProgressBar():                
                print('Computing ROTATED MODEL...')
                print('-'*80)
                print('Explainned variance...')
                self._explained_variance = self._explained_variance.compute()
                print('Squared covariance fraction...')
                self._squared_covariance_fraction = self._squared_covariance_fraction.compute()
                print('Norms...')
                self._norm1 = self._norm1.compute()
                self._norm2 = self._norm2.compute()
                print('Singular vectors...')
                self._singular_vectors1 = self._singular_vectors1.compute()
                self._singular_vectors2 = self._singular_vectors2.compute()
                print('Rotation matrix...')
                self._rotation_matrix = self._rotation_matrix.compute()
                print('Scores...')
                self._scores1 = self._scores1.compute()
                self._scores2 = self._scores2.compute()
        else:
            self._explained_variance = self._explained_variance.compute()
            self._squared_covariance_fraction = self._squared_covariance_fraction.compute()
            self._norm1 = self._norm1.compute()
            self._norm2 = self._norm2.compute()
            self._singular_vectors1 = self._singular_vectors1.compute()
            self._singular_vectors2 = self._singular_vectors2.compute()
            self._rotation_matrix = self._rotation_matrix.compute()
            self._scores1 = self._scores1.compute()
            self._scores2 = self._scores2.compute()




class ComplexMCARotator(MCARotator):
    '''Rotates a solution obtained from ``xe.models.ComplexMCA``.

    Parameters
    ----------
    n_rot : int
        Number of modes to be rotated.
    power : int
        Defines the power of Promax rotation. Choosing ``power=1`` equals
        a Varimax solution (the default is 1).
    max_iter : int
        Number of maximal iterations for obtaining the rotation matrix
        (the default is 1000).
    rtol : float
        Relative tolerance to be achieved for early stopping the iteration
        process (the default is 1e-8).
    squared_loadings : bool, default=False
        Determines the method of constructing the combined vectors of loadings. If set to True, the combined 
        vectors are loaded with the singular values ("squared loadings"), conserving the squared covariance 
        under rotation. This allows for estimation of mode importance after rotation. If set to False, 
        follows the Cheng & Dunkerton method [1]_ of loading with the square root of singular values.

    References
    ----------
    .. [1] Cheng, X., Dunkerton, T.J., 1995. Orthogonal Rotation of Spatial Patterns Derived from Singular Value Decomposition Analysis. J. Climate 8, 2631–2643. https://doi.org/10.1175/1520-0442(1995)008<2631:OROSPD>2.0.CO;2

    '''

    def transform(self, **kwargs) -> XarrayData | DataArrayList:
        raise NotImplementedError('Complex MCA does not support transform.')
    
    def components_amplitude(self) -> DataArray | Dataset | DataArrayList:
        '''Compute the amplitude of the components.

        Returns
        -------
        xr.DataArray
            Amplitude of the components.

        '''
        comps1 = abs(self._singular_vectors1)
        comps2 = abs(self._singular_vectors2)

        comps1.name = 'singular_vector_amplitude'
        comps2.name = 'singular_vector_amplitude'

        comps1 = self._model.stacker1.inverse_transform_components(comps1)
        comps2 = self._model.stacker2.inverse_transform_components(comps2)

        return comps1, comps2  # type: ignore

    def components_phase(self) -> DataArray | Dataset | DataArrayList:
        '''Compute the phase of the components.

        Returns
        -------
        xr.DataArray
            Phase of the components.

        '''
        comps1 = xr.apply_ufunc(np.angle, self._singular_vectors1)
        comps2 = xr.apply_ufunc(np.angle, self._singular_vectors2)

        comps1.name = 'singular_vector_phase'
        comps2.name = 'singular_vector_phase'

        comps1 = self._model.stacker1.inverse_transform_components(comps1)
        comps2 = self._model.stacker2.inverse_transform_components(comps2)

        return comps1, comps2  # type: ignore
    
    def scores_amplitude(self) -> DataArray | Dataset | DataArrayList:
        '''Compute the amplitude of the scores.

        Returns
        -------
        xr.DataArray
            Amplitude of the scores.

        '''
        scores1 = abs(self._scores1)
        scores2 = abs(self._scores2)

        scores1.name = 'score_amplitude'
        scores2.name = 'score_amplitude'

        scores1 = self._model.stacker1.inverse_transform_scores(scores1)
        scores2 = self._model.stacker2.inverse_transform_scores(scores2)

        return scores1, scores2  # type: ignore
    
    def scores_phase(self) -> DataArray | Dataset | DataArrayList:
        '''Compute the phase of the scores.

        Returns
        -------
        xr.DataArray
            Phase of the scores.

        '''
        scores1 = xr.apply_ufunc(np.angle, self._scores1)
        scores2 = xr.apply_ufunc(np.angle, self._scores2)

        scores1.name = 'score_phase'
        scores2.name = 'score_phase'

        scores1 = self._model.stacker1.inverse_transform_scores(scores1)
        scores2 = self._model.stacker2.inverse_transform_scores(scores2)

        return scores1, scores2  # type: ignore
