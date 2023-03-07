#include "scriptnode.h"

namespace AdGraphAPI
{
    ScriptNode::ScriptNode(std::string id,
                            std::string script_text,
                            bool is_eval_or_function) :
                                                        Node(id),
                                                        script_text_(script_text),                                                        
                                                        is_eval_or_function_(is_eval_or_function) {}

    void ScriptNode::SetEvalOrFunction(bool has_eval_or_function){
        has_eval_or_function_ = has_eval_or_function;
    }
    
    void ScriptNode::SetFingerprintingKeyword(bool has_fingerprinting_keyword){
        has_fingerprinting_keyword_ = has_fingerprinting_keyword;
    }

    void ScriptNode::SetScriptPropertiesComputedStatus(bool are_script_properties_computed){
        are_script_properties_computed_ = are_script_properties_computed;
    }

    bool ScriptNode::GetScriptPropertiesComputedStatus(){
        return are_script_properties_computed_;
    }

    int ScriptNode::GetScriptLength(){
        return script_text_.length();
    }
    
    std::string ScriptNode::GetScriptText(){
        return script_text_;
    }
    
    bool ScriptNode::GetIsEvalOrFunction(){
        return is_eval_or_function_;
    }

    bool ScriptNode::HasEvalOrFunction(){
        return has_eval_or_function_;
    }

    bool ScriptNode::HasFingerprintingKeyword(){
        return has_fingerprinting_keyword_;
    }

} // namespace AdGraphAPI


