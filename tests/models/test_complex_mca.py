import pytest
import numpy as np
import xarray as xr
import dask.array as da
from numpy.testing import assert_allclose

from xeofs.models import ComplexMCA

@pytest.fixture
def mca_model():
    return ComplexMCA(n_modes=3)

def test_complex_mca_initialization():
    mca = ComplexMCA(n_modes=1)
    assert mca is not None


@pytest.mark.parametrize('dim', [
    (('time',)),
    (('lat', 'lon')),
    (('lon', 'lat')),
    ])
def test_complex_mca_fit(mca_model, mock_data_array, dim):
    mca_model.fit(mock_data_array, mock_data_array, dim)
    assert mca_model._singular_values is not None
    assert mca_model._explained_variance is not None
    assert mca_model._squared_total_variance is not None
    assert mca_model._singular_vectors1 is not None
    assert mca_model._singular_vectors2 is not None
    assert mca_model._norm1 is not None
    assert mca_model._norm2 is not None


@pytest.mark.parametrize('dim', [
    (('time',)),
    (('lat', 'lon')),
    (('lon', 'lat')),
    ])
def test_complex_mca_components(mca_model, mock_data_array, dim):
    mca_model.fit(mock_data_array, mock_data_array, dim)
    components = mca_model.components()
    assert isinstance(components, tuple), 'components is not a tuple'
    assert len(components) == 2, 'components list does not have 2 elements'
    assert isinstance(components[0], xr.DataArray), 'components[0] is not a DataArray'
    assert isinstance(components[1], xr.DataArray), 'components[1] is not a DataArray'


@pytest.mark.parametrize('dim', [
    (('time',)),
    (('lat', 'lon')),
    (('lon', 'lat')),
    ])
def test_complex_mca_scores(mca_model, mock_data_array, dim):
    mca_model.fit(mock_data_array, mock_data_array, dim)
    scores = mca_model.scores()
    assert isinstance(scores, tuple), 'scores is not a tuple'
    assert len(scores) == 2, 'scores list does not have 2 elements'
    assert isinstance(scores[0], xr.DataArray), 'scores[0] is not a DataArray'
    assert isinstance(scores[1], xr.DataArray), 'scores[1] is not a DataArray'


@pytest.mark.parametrize('dim', [
    (('time',)),
    (('lat', 'lon')),
    (('lon', 'lat')),
    ])
def test_complex_mca_components_amplitude(mca_model, mock_data_array, dim):
    mca_model.fit(mock_data_array, mock_data_array, dim)
    components = mca_model.components_amplitude()
    assert isinstance(components, tuple), 'components is not a tuple'
    assert len(components) == 2, 'components list does not have 2 elements'
    assert isinstance(components[0], xr.DataArray), 'components[0] is not a DataArray'
    assert isinstance(components[1], xr.DataArray), 'components[1] is not a DataArray'


@pytest.mark.parametrize('dim', [
    (('time',)),
    (('lat', 'lon')),
    (('lon', 'lat')),
    ])
def test_complex_mca_components_phase(mca_model, mock_data_array, dim):
    mca_model.fit(mock_data_array, mock_data_array, dim)
    components = mca_model.components_phase()
    assert isinstance(components, tuple), 'components is not a tuple'
    assert len(components) == 2, 'components list does not have 2 elements'
    assert isinstance(components[0], xr.DataArray), 'components[0] is not a DataArray'
    assert isinstance(components[1], xr.DataArray), 'components[1] is not a DataArray'


@pytest.mark.parametrize('dim', [
    (('time',)),
    (('lat', 'lon')),
    (('lon', 'lat')),
    ])
def test_complex_mca_scores_amplitude(mca_model, mock_data_array, dim):
    mca_model.fit(mock_data_array, mock_data_array, dim)
    scores = mca_model.scores_amplitude()
    assert isinstance(scores, tuple), 'scores is not a tuple'
    assert len(scores) == 2, 'scores list does not have 2 elements'
    assert isinstance(scores[0], xr.DataArray), 'scores[0] is not a DataArray'
    assert isinstance(scores[1], xr.DataArray), 'scores[1] is not a DataArray'


@pytest.mark.parametrize('dim', [
    (('time',)),
    (('lat', 'lon')),
    (('lon', 'lat')),
    ])
def test_complex_mca_scores_phase(mca_model, mock_data_array, dim):
    mca_model.fit(mock_data_array, mock_data_array, dim)
    scores = mca_model.scores_phase()
    assert isinstance(scores, tuple), 'scores is not a tuple'
    assert len(scores) == 2, 'scores list does not have 2 elements'
    assert isinstance(scores[0], xr.DataArray), 'scores[0] is not a DataArray'
    assert isinstance(scores[1], xr.DataArray), 'scores[1] is not a DataArray'


@pytest.mark.parametrize('dim', [
    (('time',)),
    (('lat', 'lon')),
    (('lon', 'lat')),
    ])
def test_complex_mca_fit_empty_data(dim):
    mca = ComplexMCA()
    with pytest.raises(ValueError):
        mca.fit(xr.DataArray(), xr.DataArray(), dim)


@pytest.mark.parametrize('dim', [
    (('invalid_dim')),
    ])
def test_complex_mca_fit_invalid_dims(mca_model, mock_data_array, dim):
    with pytest.raises(ValueError):
        mca_model.fit(mock_data_array, mock_data_array, dim)


@pytest.mark.parametrize('dim', [
    (('time',)),
    (('lat', 'lon')),
    (('lon', 'lat')),
    ])
def test_complex_mca_transform_not_implemented(mca_model, mock_data_array, dim):
    with pytest.raises(NotImplementedError):
        mca_model.transform(mock_data_array, mock_data_array)


def test_complex_mca_homogeneous_patterns_not_implemented():
    mca = ComplexMCA()
    with pytest.raises(NotImplementedError):
        mca.homogeneous_patterns()


def test_complex_mca_heterogeneous_patterns_not_implemented():
    mca = ComplexMCA()
    with pytest.raises(NotImplementedError):
        mca.heterogeneous_patterns()


@pytest.mark.parametrize('dim', [
    (('time',)),
    (('lat', 'lon')),
    (('lon', 'lat')),
    ])
def test_complex_mca_fit_with_dataset(mca_model, mock_dataset, dim):
    mca_model.fit(mock_dataset, mock_dataset, dim)
    assert mca_model._singular_values is not None


@pytest.mark.parametrize('dim', [
    (('time',)),
    (('lat', 'lon')),
    (('lon', 'lat')),
    ])
def test_complex_mca_fit_with_dataarraylist(mca_model, mock_data_array_list, dim):
    mca_model.fit(mock_data_array_list, mock_data_array_list, dim)
    assert mca_model._singular_values is not None