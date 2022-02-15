import numpy as np
import pandas as pd
import pytest

from xeofs.models._array_transformer import _ArrayTransformer
from xeofs.pandas._dataframe_transformer import _DataFrameTransformer


@pytest.mark.parametrize('input_shape', [
    (100, 10),
])
def test_pandas_wrapper(input_shape):
    # Results of Dataframe wrapper and _ArrayTransformer match.
    rng = np.random.default_rng(7)
    arr_in = rng.standard_normal(input_shape)
    df_in = pd.DataFrame(
        arr_in,
        columns=range(1, arr_in.shape[1] + 1),
        index=range(arr_in.shape[0])
    )

    tf1 = _ArrayTransformer()
    tf1.fit(arr_in)
    arr_out = tf1.fit_transform(arr_in)
    arr_back = tf1.back_transform(arr_out)

    tf2 = _DataFrameTransformer()
    tf2.fit(df_in)
    df_out = tf2.fit_transform(df_in)
    df_back = tf2.back_transform(arr_out)

    np.testing.assert_allclose(arr_out, df_out)
    np.testing.assert_allclose(arr_back, df_back.values)


@pytest.mark.parametrize('columns', [
    ['A', 'B', 'D'],
])
def test_invalid_transform(columns):
    # Columns of new dataframe to not match fitted data.
    rng = np.random.default_rng(7)
    arr_in = rng.standard_normal((100, 3))
    df_in = pd.DataFrame(
        arr_in,
        columns=['A', 'B', 'C'],
        index=range(arr_in.shape[0])
    )

    df_new = df_in.copy()
    df_new.columns = columns

    tf = _DataFrameTransformer()
    tf.fit(df_in)
    with pytest.raises(Exception):
        _ = tf.transform(df_new)
