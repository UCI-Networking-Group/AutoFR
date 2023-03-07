#ifndef SCRIPTNODE
#define SCRIPTNODE
#include "node.h"
#include <string>

namespace AdGraphAPI
{

class ScriptNode : public Node {
  public:
    ScriptNode(std::string id, std::string script_text, bool is_eval_or_function);

    void SetEvalOrFunction(bool has_eval_or_function);
    void SetFingerprintingKeyword(bool has_fingerprinting_keyword);
    void SetScriptPropertiesComputedStatus(bool are_script_properties_computed);

    std::string GetScriptText();
    bool GetScriptPropertiesComputedStatus();
    int GetScriptLength();
    bool GetIsEvalOrFunction();
    bool HasEvalOrFunction();
    bool HasFingerprintingKeyword();
        
  private:
    std::string script_text_;
    bool is_eval_or_function_;
    bool has_eval_or_function_;
    bool has_fingerprinting_keyword_;    

    bool are_script_properties_computed_ = false;
};

} // namespace AdGraphAPI
#endif // SCRIPTNODE