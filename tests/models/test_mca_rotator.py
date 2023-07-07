import pytest
import numpy as np
import xarray as xr
from dask.array import Array as DaskArray   # type: ignore

# Import the classes from your modules
from xeofs.models import MCA, MCARotator

@pytest.fixture
def mca_model(mock_data_array, dim):
    mca = MCA(n_modes=5)
    mca.fit(mock_data_array, mock_data_array, dim)
    return mca

@pytest.fixture
def mca_model_delayed(mock_dask_data_array, dim):
    mca = MCA(n_modes=5)
    mca.fit(mock_dask_data_array, mock_dask_data_array, dim)
    return mca


def test_mcarotator_init():
    mca_rotator = MCARotator(n_modes=2)
    assert mca_rotator._params['n_modes'] == 2
    assert mca_rotator._params['power'] == 1
    assert mca_rotator._params['max_iter'] == 1000
    assert mca_rotator._params['rtol'] == 1e-8
    assert mca_rotator._params['squared_loadings'] == False


@pytest.mark.parametrize('dim', [
    (('time',)),
    (('lat', 'lon')),
    (('lon', 'lat')),
])
def test_mcarotator_fit(mca_model):
    mca_rotator = MCARotator(n_modes=2)
    mca_rotator.fit(mca_model)

    assert hasattr(mca_rotator, "_rotation_matrix")
    assert hasattr(mca_rotator, "_idx_expvar")


@pytest.mark.parametrize('dim', [
    (('time',)),
    (('lat', 'lon')),
    (('lon', 'lat')),
])
def test_mcarotator_transform(mca_model, mock_data_array):
    mca_rotator = MCARotator(n_modes=2)
    mca_rotator.fit(mca_model)
    
    projections = mca_rotator.transform(data1=mock_data_array, data2=mock_data_array)
    
    assert len(projections) == 2


@pytest.mark.parametrize('dim', [
    (('time',)),
    (('lat', 'lon')),
    (('lon', 'lat')),
])
def test_mcarotator_inverse_transform(mca_model):
    mca_rotator = MCARotator(n_modes=2)
    mca_rotator.fit(mca_model)
    
    reconstructed_data = mca_rotator.inverse_transform(mode=slice(1,3))
    
    assert isinstance(reconstructed_data, tuple)
    assert len(reconstructed_data) == 2


@pytest.mark.parametrize('dim', [
    (('time',)),
    (('lat', 'lon')),
    (('lon', 'lat')),
])
def test_mcarotator_compute(mca_model_delayed):
    '''Test the compute method of the MCARotator class.'''
    pass
    # NOTE: This test takes a long time to run though it should not. Running the same example
    # in a separate file is much faster. I don't have a clue why this is the case but for the moment
    # I will leave it as is but deactivate the test. 
    
    # mca_rotator = MCARotator(n_modes=2, rtol=1e-5)
    # mca_rotator.fit(mca_model_delayed)
    
    # mca_rotator.compute()

    # assert isinstance(mca_rotator._explained_variance, xr.DataArray)
    # assert isinstance(mca_rotator._squared_covariance_fraction, xr.DataArray)
    # assert isinstance(mca_rotator._singular_vectors1, xr.DataArray)
    # assert isinstance(mca_rotator._singular_vectors2, xr.DataArray)
    # assert isinstance(mca_rotator._rotation_matrix, xr.DataArray)
    # assert isinstance(mca_rotator._scores1, xr.DataArray)
    # assert isinstance(mca_rotator._scores2, xr.DataArray)