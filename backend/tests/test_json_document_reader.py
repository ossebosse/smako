from __future__ import annotations

import io
import json

import pytest
from app.services.json_document_reader import JsonDocumentReader


@pytest.mark.parametrize('chunk_size',[1,2,7,64,65536])
@pytest.mark.parametrize('value',[
    {'a':[0,12,-345,1.25,1e-18,True,False,None], 'empty':{}, 'z':[]},
    {'quote':'a"b\\c\n\t','unicode':'räksås 🍋','nested':[{'x':[1,2,3]}]},
    {'number':123456789012345678901234567890,'exponent':1.234e100},
])
def test_incremental_containers_equal_standard_decoder_across_chunk_boundaries(chunk_size,value):
    raw = json.dumps(value,ensure_ascii=False)
    reader = JsonDocumentReader(io.StringIO(raw+'\n '),chunk_size=chunk_size)
    result = reader.object({'a':lambda:reader.array(reader.value),
                            'nested':lambda:reader.array(lambda:reader.object({}))})
    reader.finish()
    assert result == json.loads(raw)


@pytest.mark.parametrize('raw',[
    '{"a":[1,]}','{"a":1,}','{"a":1e+}','{"a":12x}',
    '{"a":truefalse}','{"a":"bad\nline"}','{"a":1}junk','{"a":[1',
    '{false:1}','{"a":01}','{"a":1 2}',
    '{"a":"\\ud800"}','{"\\udc00":1}','\ufeff{"a":1}',
])
def test_malformed_or_incomplete_json_is_never_a_complete_document(raw):
    reader = JsonDocumentReader(io.StringIO(raw),chunk_size=1)
    with pytest.raises(ValueError):
        reader.object({'a':lambda:reader.array(reader.value)})
        reader.finish()


def test_duplicate_keys_follow_native_json_last_value_behavior():
    raw = '{"a":[1],"a":[2],"b":{"c":1,"c":2}}'
    reader = JsonDocumentReader(io.StringIO(raw),chunk_size=3)
    result = reader.object({'a':lambda:reader.array(reader.value),'b':lambda:reader.object({})})
    reader.finish()
    assert result == json.loads(raw)


def test_rows_are_validated_before_reading_the_complete_array():
    raw = json.dumps({'a':[{'n':i,'value':'x'*100} for i in range(1000)]})
    source = io.StringIO(raw)
    reader = JsonDocumentReader(source,chunk_size=128)
    observed = []

    def validate(row):
        observed.append(source.tell())
        return json.loads(row)

    result = reader.object({'a':lambda:reader.array(lambda:reader.value(validate))})
    reader.finish()
    assert result == json.loads(raw)
    assert observed[0] < len(raw)//100
    assert len(observed) == 1000
