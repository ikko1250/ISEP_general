from sudachipy import tokenizer
from sudachipy import dictionary
import sys
import os

# Add current directory to path
sys.path.append('/home/ubuntu/cur/isep')
from analyze_text_sudachi import evaluate_rule, find_token_intervals

def test():
    tokenizer_obj = dictionary.Dictionary(dict="core").create()
    mode = tokenizer.Tokenizer.SplitMode.C
    
    text = "(説明会の開催)第8条事業者は、次条の規定による協議を行う前までに、住民等に対し、事業に関する説明会を開催しなければならない。"
    morphemes = tokenizer_obj.tokenize(text, mode)
    
    print(f"Text: {text}")
    
    surfaces = [m.surface() for m in morphemes]
    dict_forms = [m.dictionary_form() for m in morphemes]
    normalized_forms = [m.normalized_form() for m in morphemes]
    token_starts = set(m.begin() for m in morphemes)
    token_ends = set(m.end() for m in morphemes)
    
    rule = "((住民 or 近隣 or 関係住民 or 地域住民) and (説明会 or 説明の場 or 説明)) or near(説明会-実施)[6] or 周知"
    
    print(f"\nTesting Rule: {rule}")
    result = evaluate_rule(text, surfaces, dict_forms, normalized_forms, token_starts, token_ends, rule)
    print(f"Result: {result}")
    
    # Debug individual components
    print("\n--- Debugging Components ---")
    print(f"Check '住民': {evaluate_rule(text, surfaces, dict_forms, normalized_forms, token_starts, token_ends, '住民')}")
    print(f"Check '説明会': {evaluate_rule(text, surfaces, dict_forms, normalized_forms, token_starts, token_ends, '説明会')}")
    print(f"Check 'near(説明会-実施)[6]': {evaluate_rule(text, surfaces, dict_forms, normalized_forms, token_starts, token_ends, 'near(説明会-実施)[6]')}")
    print(f"Check '周知': {evaluate_rule(text, surfaces, dict_forms, normalized_forms, token_starts, token_ends, '周知')}")

if __name__ == "__main__":
    test()
