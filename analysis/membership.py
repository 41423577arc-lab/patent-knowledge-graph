"""Vectorized membership for P3 Arrow string IDs, with pandas semantics fallback."""
import pyarrow as pa
import pyarrow.compute as pc


def member_of(series,values):
    array=series.array
    if hasattr(array,"__arrow_array__"):
        arrow=array.__arrow_array__()
        if pa.types.is_string(arrow.type) or pa.types.is_large_string(arrow.type):
            try:
                candidates=list(values) if isinstance(values,(set,frozenset)) else values
                candidates=pa.array(candidates,type=arrow.type,from_pandas=True)
                return pc.is_in(arrow,value_set=candidates).to_numpy(zero_copy_only=False)
            except (pa.ArrowInvalid,pa.ArrowTypeError,TypeError):
                # Mixed non-string candidates have pandas-defined comparison semantics.
                pass
    return series.isin(values)
